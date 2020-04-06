
add_executable(simulator
    main.cpp
)

target_compile_options(simulator PRIVATE
    ${COMMON_COMPILE_FLAGS}
    ${TARGET_COMPILE_FLAGS}
)

target_link_libraries(simulator
    Vmyfpga
)
