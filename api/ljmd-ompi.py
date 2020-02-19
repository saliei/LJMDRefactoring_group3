from __future__ import print_function
import sys as _sys
from ctypes import *
from mpi4py import MPI
import os

""" ljmd.py: Wrapper for ljmd.c code
This is a wrapper around Leonard-Jones Molecular Dynamics codes 
written in c. for a description on how to use the wrapper 
refer to the project website at:
https://github.com/saliei/LJMDRefactoring_group3
"""
__author__      =   "Saeid Aliei"
__copyright__   =   "Copyright 2020, ICTP-MHPC"
__licence__     =   "GPL"
__version__     =   "1.0.0"
__maintainer__  =   "Saeid Aliei"
__email__       =   "saeidaliei2019@gmail.com"
__date__        =   "Feb 2020"
__state__       =   "Dev"

if MPI._sizeof(MPI.Comm) == sizeof(c_int):
    MPI_Comm = c_int
else:
    MPI_Comm = c_void_p

class Mdsys(Structure):
    """Wrapper around _mdsys structure.

    __fields__ represents the variables present
    in the _mdsys structure on the C side in the order
    they appear.
    
    Attributes
    ----------
    natoms: int
        number of atoms present in the system
    nfi: int
        step of the simulation
    nsteps: int
        number of steps to evolve the system
    dt: float
        time step of simulation
    mass: float
        mass of each molecule in AMU units
    epsilon: float
        constant in kcal/mol units
    rcut: float
        potential reach, after this force is zero, in units of Angstrom
    ekin: float
        kinetic energy of the system
    epot: float
        potential energy of the system
    temp: float
        temperature of the system
    rx: pointer(double)
        pointer to the array of x positions of the system
    ry: pointer(double)
        pointer to the array of y positions of the system
    rz: pointer(double)
        pointer to the array of z positions of the system
    vx: pointer(double)
        pointer to the array of x velocities of the system
    vy: pointer(double)
        pointer to the array of y velocities of the system
    vz: pointer(double)
        pointer to the array of z velocities of the system
    fx: pointer(double)
        pointer to the array of x velocities of the system
    fy: pointer(double)
        pointer to the array of y velocities of the system
    fz: pointer(double)
        pointer to the array of z velocities of the system
    """
    _fields_ = [
        ("natoms", c_int),
        ("nfi", c_int),
        ("nsteps", c_int),
        ("dt", c_double),
        ("mass", c_double),
        ("epsilon", c_double),
        ("sigma", c_double),
        ("box", c_double),
        ("rcut", c_double),
        ("ekin", c_double),
        ("epot", c_double),
        ("temp", c_double),
        ("rx", POINTER(c_double)),
        ("ry", POINTER(c_double)),
        ("rz", POINTER(c_double)),
        ("vx", POINTER(c_double)),
        ("vy", POINTER(c_double)),
        ("vz", POINTER(c_double)),
        ("fx", POINTER(c_double)),
        ("fy", POINTER(c_double)),
        ("fz", POINTER(c_double)),
        ("cx", POINTER(c_double)),
        ("cy", POINTER(c_double)),
        ("cz", POINTER(c_double)),
        ("mpirank", c_int),
        ("nprocs", c_int),
        ("nthreads", c_int),
        ("mpicomm", MPI_Comm),
        ]

class Ljmd:
    """LJMD object to define a system of particles.

    Ljmd class defines mehodes to interact with the 
    Molecular Dynamic system.

    """
    def __init__(self, initfile):
        """Initialize Ljmd object.
        
        Arguments
        ---------
        initfile: str
            initialization file, it will look it under examples dir

        """
        self.initfile = initfile
        try:
            self._dll = CDLL("../obj/libljmd.so")
            print("Shared object loaded.")
        except Exception as err:
            print("Could not load shared object: {}".format(str(err)))
            _sys.exit(1)
        self.sys = Mdsys()
        self.initompi()
        self.loadinit()
        self.sysinit()

    def loadinit(self):
        """Load initialization file."""
        if(self.sys.mpirank == 0):
            try:
                with open("inits/"+self.initfile, 'r') as file:
                    self.args = [line.split("#",1)[0].rstrip() for line in file]
            except Exception as err:
                print("Error reading init file: {}".format(str(err)))
                _sys.exit(1)
            self.natoms = int(self.args[0])
            self.mass = float(self.args[1])
            self.epsilon = float(self.args[2])
            self.sigma = float(self.args[3])
            self.rcut = float(self.args[4])
            self.box = float(self.args[5])
            self.restfile = str(self.args[6])
            self.trajfile = str(self.args[7])
            self.ergfile = str(self.args[8])
            self.nsteps = int(self.args[9])
            self.dt = float(self.args[10])
            self.nprint = int(self.args[11])
            print("\nLoaded init file.")
        self.natoms = self.comm.bcast(self.natoms, root=0)
        self.mass = self.comm.bcast(self.mass, root=0)
        self.epsilon = self.comm.bcast(self.epsilon, root=0)
        self.sigma = self.comm.bcast(self.sigma, root=0)
        self.rcut = self.comm.bcast(self.rcut, root=0)
        self.box = self.comm.bcast(self.box, root=0)
        self.nsteps = self.comm.bcast(self.nsteps, root=0)
        self.dt = self.comm.bcast(self.dt, root=0)

    def initompi(self):
        """Handle OpenMP and MPI initialization"""
        self.comm = MPI.COMM_WORLD
        _comm_ptr = MPI._addressof(self.comm)
        _comm_val = MPI_Comm.from_address(_comm_ptr)
        self.sys.mpicomm = _comm_val
        self.sys.mpirank = self.comm.Get_rank()
        self.sys.nprocs = self.comm.Get_size()
        try:
            _omp_num_threads = int(os.environ['OMP_NUM_THREADS'])
        except Exception as err:
            print("Couldn't read enviromental variable OMP_NUM_THREADS: {}"
                .format(str(err)))
            print("Setting OMP_NUM_THREADS = 1")
            _omp_num_threads = 1
        self.sys.nthreads = _omp_num_threads

    def sysinit(self):
        """Initialize system as Mdsys instance.

        Defines position, velocity and force as ctype double,
        then loads the restart file and initializes force and
        kinetic energy of the system.

        """
        self.sys.rx = (c_double * self.natoms)()
        self.sys.ry = (c_double * self.natoms)()
        self.sys.rz = (c_double * self.natoms)()
        self.sys.vx = (c_double * self.natoms)()
        self.sys.vy = (c_double * self.natoms)()
        self.sys.vz = (c_double * self.natoms)()
        self.sys.cx = (c_double * self.natoms * self.sys.nthreads)()
        self.sys.cy = (c_double * self.natoms * self.sys.nthreads)()
        self.sys.cz = (c_double * self.natoms * self.sys.nthreads)()
        if (self.sys.mpirank == 0):
            self.loadrest()
            self.sys.fx = (c_double * self.natoms)()
            self.sys.fy = (c_double * self.natoms)()
            self.sys.fz = (c_double * self.natoms)()
        self.comm.barrier()
        self.sys.nfi = 0
        self.force()
        # if(self.sys.mpirank == 0):
        #     self.ekin()
        print("System initialized.")

    def force(self):
        self._dll.force(byref(self.sys))

    def ekin(self):
        self._dll.ekin(byref(self.sys))

    def velverlet(self):
        self._dll.velverlet(byref(self.sys))

    def update_velocities_positions(self):
        self.__dll.update_velocities_positions(byref(self.sys))

    def update_velocities(self):
        self._dll.update_velocities(byref(self.sys))
    
    def runompisim(self):
        """Run simulation of the system.

        This method in turn will call velverlet and ekin function
        on the C side. it will evolve the system for nstep times.

        """
        if (self.sys.mpirank == 0):
            self.ekin()
            print("\nStarting simulation with {} atoms for {} steps.".format(
                self.natoms, self.nsteps))
            print("NFI \t\t\t TEMP \t\t EKIN \t\t  EPOT \t\t\t ETOT")
            self.output()
        self.sys.nfi = 1
        while self.sys.nfi <= self.sys.nsteps:
            if(self.sys.nfi % self.nprint == 0) and (self.sys.mpirank == 0):
                self.output()
            if(self.sys.mpirank == 0):
                self.update_velocities_positions()
            self.force()
            if(self.sys.mpirank == 0):
                self.update_velocities()
                self.ekin()
            self.sys.nfi += 1
            if(self.sys.mpirank == 0):
                print("Simulation done!")

    def loadrest(self):
        """Loads restart file and initializes positions and velocities."""
        try:
            with open("inits/"+self.restfile, "r") as file:
                line  = file.readlines()
                assert len(line) == 2 * self.natoms, \
                "Restart file is not correct.\n"
                for i in range(self.natoms):
                    self.sys.rx[i] = float(line[i].rstrip().split()[0])
                    self.sys.ry[i] = float(line[i].rstrip().split()[1])
                    self.sys.rz[i] = float(line[i].rstrip().split()[2])
                for i in range(self.natoms):
                    self.sys.vx[i] = float(line[i+self.natoms].rstrip().split()[0])
                    self.sys.vy[i] = float(line[i+self.natoms].rstrip().split()[1])
                    self.sys.vz[i] = float(line[i+self.natoms].rstrip().split()[2])
        except Exception as err:
            print("Could not read restart file: {}".format(str(err)))
            _sys.exit(1)

    def output(self):
        """Write energy and positions results to given files."""
        _ergstr = "%8d %20.8f %20.8f %20.8f %20.8f" %(
            self.sys.nfi, self.sys.temp, self.sys.ekin, self.sys.epot, 
            self.sys.ekin+self.sys.epot)
        print(_ergstr)
        try:
            with open("results/"+self.ergfile, "a") as file:
                file.write(_ergstr+"\n")
        except Exception as err:
            print("Error writing to file: {}".format(str(err)))

        try:
            with open("results/"+self.trajfile, "a") as file:
                file.write("\nnfi = {} \t etot = {:.8}\n".format(
                    self.sys.nfi, self.sys.ekin+self.sys.epot))
                for i in range(self.natoms):
                    _trajstr = "Ar  %20.8f %20.8f %20.8f\n" %(
                        self.sys.rx[i], self.sys.ry[i], self.sys.rz[i])
                    file.write(_trajstr)
        except Exception as err:
            print("Error writing to file: {}".format(str(err)))


if __name__ == '__main__':
        md = Ljmd("argon_003.inp")
        md.runompisim()    