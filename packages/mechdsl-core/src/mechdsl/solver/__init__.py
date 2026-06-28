"""Newton driver, linear solver adapter, mesh I/O, load stepping."""

from mechdsl.solver.history_fields import HistoryFields, create_j2_history
from mechdsl.solver.import_adapter import (
    Algo2CodePCGSolver,
    CGSolver,
    LinearSolverInterface,
    PCGSolver,
    ScipyCGSolver,
    build_solver,
    get_default_solver,
    make_seam_solver,
)
from mechdsl.solver.integration import select_linear_solver
from mechdsl.solver.jacobi_preconditioner import GeneratedJacobiPreconditioner
from mechdsl.solver.load_stepping import (
    LoadSteppingConfig,
    LoadSteppingResult,
    LoadStepResult,
    adaptive_load_stepping,
)
from mechdsl.solver.mesh_io import (
    HexMesh,
    generate_cook_membrane_mesh,
    generate_hex8_mesh,
    generate_necking_bar_mesh,
    get_face_nodes,
)
from mechdsl.solver.newton import NewtonConfig, NewtonResult, newton_solve
from mechdsl.solver.seam_integrate import (
    bind_generated_newmark_integrator,
    build_seam_newmark,
    newmark_tex_path,
    transpile_seam_newmark,
)
from mechdsl.solver.seam_solve import (
    bind_generated_pcg_solver,
    build_seam_pcg,
    pcg_tex_path,
    transpile_seam_pcg,
)

__all__ = [
    "Algo2CodePCGSolver",
    "CGSolver",
    "GeneratedJacobiPreconditioner",
    "HexMesh",
    "HistoryFields",
    "LinearSolverInterface",
    "LoadStepResult",
    "LoadSteppingConfig",
    "LoadSteppingResult",
    "NewtonConfig",
    "NewtonResult",
    "PCGSolver",
    "ScipyCGSolver",
    "adaptive_load_stepping",
    "bind_generated_newmark_integrator",
    "bind_generated_pcg_solver",
    "build_seam_newmark",
    "build_seam_pcg",
    "build_solver",
    "create_j2_history",
    "generate_cook_membrane_mesh",
    "generate_hex8_mesh",
    "generate_necking_bar_mesh",
    "get_default_solver",
    "get_face_nodes",
    "make_seam_solver",
    "newmark_tex_path",
    "newton_solve",
    "pcg_tex_path",
    "select_linear_solver",
    "transpile_seam_newmark",
    "transpile_seam_pcg",
]
