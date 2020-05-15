
module myfpga(
    input logic i_LogicClock,


    input logic i_ConfigActive,
    input logic i_ConfigData,
    input logic i_ConfigClock,

    input logic [WIDTH+1:0] i_IO_North,
    output logic [WIDTH+1:0] o_IO_North,
    input logic [WIDTH+1:0] i_IO_South,
    output logic [WIDTH+1:0] o_IO_South,
    input logic [HEIGHT+1:0] i_IO_West,
    output logic [HEIGHT+1:0] o_IO_West,
    input logic [HEIGHT+1:0] i_IO_East,
    output logic [HEIGHT+1:0] o_IO_East
);

parameter WIDTH = 10;
parameter HEIGHT = 10;

endmodule




// module logic_cell_wrapper (


// );
//     // Wrap a logic cell with the input muxes for selecting the
//     // logic cell input signals from the surrounding switch blocks,
//     // as well as distributing the output signal to those switch blocks.

// endmodule









