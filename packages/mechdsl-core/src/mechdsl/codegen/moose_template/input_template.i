# MOOSE input file emitted from MechDSL (Plan B Phase 8, Task P8-2).
#
# Placeholders are filled by mechdsl.codegen.moose_printer.emit_input_file.
# DO NOT edit the placeholders by hand — regenerate via the printer.
#
# This deck wires a simple tension test (uniaxial pull along +x) into the
# emitted `{{MATERIAL_NAME}}` ComputeStressBase subclass. The mesh is a unit
# cube of Hex8 elements; Young's modulus and Poisson's ratio are baked into
# material properties at input-file parse time.

[Mesh]
  type = GeneratedMesh
  dim = 3
  nx = {{MESH_NX}}
  ny = {{MESH_NY}}
  nz = {{MESH_NZ}}
  xmin = 0.0
  xmax = 1.0
  ymin = 0.0
  ymax = 1.0
  zmin = 0.0
  zmax = 1.0
  elem_type = HEX8
[]

[GlobalParams]
  displacements = 'disp_x disp_y disp_z'
[]

[Variables]
  [disp_x]
  []
  [disp_y]
  []
  [disp_z]
  []
[]

[Kernels]
  [TensorMechanics]
    displacements = 'disp_x disp_y disp_z'
    use_displaced_mesh = false
  []
[]

[BCs]
  # Tension test: fix the x=0 face, pull the x=1 face along +x.
  [fix_x]
    type = DirichletBC
    variable = disp_x
    boundary = left
    value = 0.0
  []
  [fix_y]
    type = DirichletBC
    variable = disp_y
    boundary = bottom
    value = 0.0
  []
  [fix_z]
    type = DirichletBC
    variable = disp_z
    boundary = back
    value = 0.0
  []
  [pull_x]
    type = FunctionDirichletBC
    variable = disp_x
    boundary = right
    function = '{{PULL_AMPLITUDE}} * t'
  []
[]

[Materials]
  [{{MATERIAL_NAME}}_material]
    type = {{MATERIAL_NAME}}
    youngs_modulus = {{YOUNGS_MODULUS}}
    poissons_ratio = {{POISSONS_RATIO}}
    # Material model: {{MATERIAL_MODEL}}
    # Formulation:    {{FORMULATION}}
    block = 0
  []
  [strain]
    type = ComputeFiniteStrain
    displacements = 'disp_x disp_y disp_z'
    block = 0
  []
[]

[Preconditioning]
  [SMP]
    type = SMP
    full = true
  []
[]

[Executioner]
  type = Transient
  solve_type = NEWTON
  petsc_options_iname = '-pc_type'
  petsc_options_value = 'lu'
  nl_rel_tol = 1e-10
  nl_abs_tol = 1e-10
  l_tol = 1e-8
  dt = {{TIME_STEP}}
  num_steps = {{NUM_STEPS}}
[]

[Outputs]
  exodus = true
  console = true
[]
