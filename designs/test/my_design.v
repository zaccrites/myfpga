
module my_design (
    input i_Clock,
    input i_Reset,
    input [15:0] i_Amount,
    output [15:0] o_Output
);


always @ (posedge i_Clock) begin
    if (i_Reset) begin
        o_Output <= 0;
    end
    else begin
        o_Output <= o_Output + i_Amount;
    end
end


endmodule
