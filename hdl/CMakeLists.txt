
set(VERILATOR_OUTPUT_DIR ${CMAKE_CURRENT_BINARY_DIR}/verilator_output)
set(VERILATOR_INCLUDE_DIR "/usr/share/verilator/include")

set(VMYFPGA_SOURCE_FILES
    "${VERILATOR_OUTPUT_DIR}/Vmyfpga.cpp"
    # "${VERILATOR_OUTPUT_DIR}/Vmyfpga___024unit.cpp"
    "${VERILATOR_OUTPUT_DIR}/Vmyfpga__Syms.cpp"
)

add_library(Vmyfpga
    ${VMYFPGA_SOURCE_FILES}
    "${VERILATOR_INCLUDE_DIR}/verilated.cpp"
)

target_include_directories(Vmyfpga SYSTEM PUBLIC
    ${VERILATOR_OUTPUT_DIR}
    ${VERILATOR_INCLUDE_DIR}
)

target_compile_options(Vmyfpga PRIVATE
    -Os
    -fdiagnostics-color
)

set_target_properties(Vmyfpga PROPERTIES
    CXX_STANDARD 17
    CXX_EXTENSIONS OFF
)

add_custom_command(
    COMMAND
        ${CMAKE_COMMAND} -E make_directory ${VERILATOR_OUTPUT_DIR}
    COMMAND
        verilator_bin -cc "${CMAKE_CURRENT_SOURCE_DIR}/myfpga.sv"
        --stats
        --MMD --Mdir ${VERILATOR_OUTPUT_DIR}
        -I${CMAKE_CURRENT_SOURCE_DIR}
        -Wall -Werror-width -Werror-selrange -Werror-implicit -Werror-pinmissing

    OUTPUT
        ${VMYFPGA_SOURCE_FILES}

    DEPENDS
        "${CMAKE_CURRENT_SOURCE_DIR}/myfpga.sv"
        "${CMAKE_CURRENT_SOURCE_DIR}/logic_cell.sv"
        "${CMAKE_CURRENT_SOURCE_DIR}/slice.sv"
        "${CMAKE_CURRENT_SOURCE_DIR}/lut.sv"

        "${CMAKE_CURRENT_SOURCE_DIR}/mux8.sv"
        "${CMAKE_CURRENT_SOURCE_DIR}/shift_register8.sv"

    VERBATIM
)
