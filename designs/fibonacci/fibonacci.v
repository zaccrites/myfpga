
module fibonacci (
    input i_Clock,
    input i_Reset,
    output reg [15:0] r_Value
);

reg [4:0] r_Counter;
reg [15:0] r_A;
reg [15:0] r_B;

always @ (posedge i_Clock) begin
    if (i_Reset || r_Counter > 23) begin
        r_Value <= 0;
        r_A <= 0;
        r_B <= 1;
        r_Counter <= 0;
    end
    else begin
        r_Value <= r_B;
        r_A <= r_B;
        r_B <= r_A + r_B;
        r_Counter <= r_Counter + 1;
    end
end

endmodule
