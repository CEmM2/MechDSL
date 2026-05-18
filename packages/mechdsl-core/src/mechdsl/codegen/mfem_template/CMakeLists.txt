# =====================================================================
# MechDSL-generated MFEM application — hand-rolled CMakeLists template.
#
# Placeholders:
#   @MECHDSL_EXE_NAME@   Executable name filled in by emit_cmakelists().
#
# Usage:
#   mkdir build && cd build
#   cmake -DMFEM_DIR=/path/to/mfem/build ..
#   cmake --build . -j
# =====================================================================

cmake_minimum_required(VERSION 3.16)
project(mechdsl_mfem_app LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Honour the MFEM install prefix a user passes via -DMFEM_DIR=... and fall
# back to the in-tree build layout that upstream MFEM ships.
find_package(MFEM REQUIRED CONFIG
   HINTS
      ${MFEM_DIR}
      ${MFEM_DIR}/lib/cmake/mfem
      $ENV{MFEM_DIR}
      $ENV{MFEM_DIR}/lib/cmake/mfem
)

# MPI is required for mfem::ParNonlinearForm.
find_package(MPI REQUIRED)

set(MECHDSL_EXE_NAME "@MECHDSL_EXE_NAME@")
if(MECHDSL_EXE_NAME STREQUAL "@MECHDSL_EXE_NAME@")
   set(MECHDSL_EXE_NAME "mechdsl_mfem_app")
endif()

add_executable(${MECHDSL_EXE_NAME} main.cpp)

target_include_directories(${MECHDSL_EXE_NAME} PRIVATE
   ${MFEM_INCLUDE_DIRS}
)

target_link_libraries(${MECHDSL_EXE_NAME} PRIVATE
   mfem
   MPI::MPI_CXX
)

target_compile_definitions(${MECHDSL_EXE_NAME} PRIVATE
   MFEM_USE_MPI=1
)
