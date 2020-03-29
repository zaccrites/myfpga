
module myfpga (
    input logic i_Clock,

    // verilator lint_off UNUSED
    input logic i_Reset,
    // verilator lint_on UNUSED

    output o_Output
);



logic [7:0] r_Counter;
assign o_Output = r_Counter[7];


always_ff @ (posedge i_Clock) begin

    if (i_Reset) begin
        r_Counter <= 0;
    end
    else begin
        r_Counter <= r_Counter + 1;
    end

end



endmodule
