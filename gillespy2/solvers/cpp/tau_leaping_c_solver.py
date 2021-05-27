import numpy

from gillespy2.solvers.cpp.c_decoder import BasicSimDecoder
from gillespy2.solvers.utilities import solverutils as cutils
from gillespy2.core import GillesPySolver, gillespyError, Model

from .c_simulation import CSimulation, SimulationReturnCode

class TauLeapingCSolver(GillesPySolver, CSimulation):
    name = "TauLeapingCSolver"
    type = "TauLeapingSimulation"

    def get_solver_settings(self):
        """
        :return: Tuple of strings, denoting all keyword argument for this solvers run() method.
        """
        return ('model', 't', 'number_of_trajectories', 'timeout', 'increment', 'seed', 'debug', 'profile')

    def run(self=None, model: Model = None, t: int = 20, number_of_trajectories: int = 1, timeout: int = 0,
            increment: int = 0.05, seed: int = None, debug: bool = False, profile: bool = False, variables={}, 
            resume=None, tau_step: int = .03, **kwargs):

        if self is None or self.model is None:
            self = TauLeapingCSolver(model, resume=resume)

        # Validate parameters prior to running the model.
        self._validate_type(variables, dict, "'variables' argument must be a dictionary.")
        self._validate_variables_in_set(variables, self.species + self.parameters)
        self._validate_resume(t, resume)
        self._validate_kwargs(**kwargs)
        self._validate_sbml_features({
            "Rate Rules": len(model.listOfRateRules),
            "Assignment Rules": len(model.listOfAssignmentRules),
            "Events": len(model.listOfEvents),
            "Function Definitions": len(model.listOfFunctionDefinitions)
        })

        if resume is not None:
            t = abs(t - int(resume["time"][-1]))

        number_timesteps = int(round(t / increment + 1))

        args = {
            "trajectories": number_of_trajectories,
            "timesteps": number_timesteps,
            "tau_step": tau_step,
            "end": t
        }

        if self.variable:
            populations = cutils.update_species_init_values(model.listOfSpecies, self.species, variables, resume)
            parameter_values = cutils.change_param_values(model.listOfParameters, self.parameters, model.volume, variables)

            args.update({
                "initial_values": populations,
                "parameters": parameter_values
            })

        seed = self._validate_seed(seed)
        if seed is not None:
            args.update({
                "seed": seed
            })


        args = self._make_args(args)
        decoder = BasicSimDecoder.create_default(number_of_trajectories, number_timesteps, len(self.model.listOfSpecies))

        sim_exec = self._build(model, self.type, self.variable, False)
        sim_status = self._run(sim_exec, args, decoder, timeout)

        if sim_status == SimulationReturnCode.FAILED:
            raise gillespyError.ExecutionError("Error encountered while running simulation C++ file:\n"
                f"Return code: {int(sim_status)}.\n")

        trajectories, time_stopped = decoder.get_output()

        simulation_data = self._format_output(trajectories)
        simulation_data = self._make_resume_data(time_stopped, simulation_data, t, resume)

        return simulation_data, int(sim_status)