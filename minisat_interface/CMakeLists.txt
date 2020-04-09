
add_executable(minisat_interface
    main.cpp
)

target_link_libraries(minisat_interface
    /usr/lib/libminisat.a
)

target_include_directories(minisat_interface PRIVATE SYSTEM
    /usr/include/minisat
)

target_compile_options(minisat_interface PRIVATE
    -O2
    -fdiagnostics-color
    -Wall
    -Wextra
)
