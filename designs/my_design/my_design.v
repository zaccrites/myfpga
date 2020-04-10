
module my_design (
    input i_Clock,
    input i_Reset,
    output [3:0] o_Data
);

always @ (posedge i_Clock) begin
    o_Data <= i_Reset ? 0 : (o_Data + 1);
end

endmodule
