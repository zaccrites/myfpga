
find_package(SDL2 REQUIRED)

add_executable(simulator
    main.cpp
    # Goose.cpp
)

target_compile_options(simulator PRIVATE
    ${COMMON_COMPILE_FLAGS}
    ${TARGET_COMPILE_FLAGS}
)

target_link_libraries(simulator
    ${SDL2_LIBRARIES}
    Vmyfpga
)
