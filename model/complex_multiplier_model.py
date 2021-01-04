from fixedpoint import FixedPoint
from bitstring import BitArray

class Model:
    def __init__(self, input_width_a, input_width_b, output_width , truncate):
        self.input_width_a = input_width_a
        self.input_width_b = input_width_b
        self.output_width = output_width
        self.truncate = truncate

        self.axis_input_width_a = ((self.input_width_a+15)//16)*16
        self.axis_input_width_b = ((self.input_width_b+15)//16)*16
        self.axis_output_width  = ((self.output_width+15)//16)*16        

    def calculate(self, a, b, rounding_cy=0):
        signFlag = True
        byteOrder = 'big'
        bitOrder = 'big'
        # endian parameter fir BitArray seems to matter only for bits but not for bytes
        # so bytes have to be reversed manually here
        # use FixPoint to select the used bits
        a_i = FixedPoint(int.from_bytes(a[0:self.axis_input_width_a//2//8],byteorder='big', signed=signFlag), signed=signFlag,m=self.input_width_a//2,n=0)
        a_r = FixedPoint(int.from_bytes(a[self.axis_input_width_a//2//8:],byteorder='big', signed=signFlag), signed=signFlag,m=self.input_width_a//2,n=0)
        b_i = FixedPoint(int.from_bytes(b[0:self.axis_input_width_b//2//8],byteorder='big', signed=signFlag), signed=signFlag,m=self.input_width_b//2,n=0)
        b_r = FixedPoint(int.from_bytes(b[self.axis_input_width_b//2//8:],byteorder='big', signed=signFlag), signed=signFlag,m=self.axis_input_width_b//2,n=0)
        r_r = int(a_r*b_r) - int(a_i*b_i)
        r_i = int(a_r*b_i) + int(a_i*b_r)
        
        # truncate
        # its important to do truncation after the + and - operation, 
        # if truncation is done before that, the result is slightly different!
        truncate_bits = self.input_width_a + self.input_width_b - self.output_width
        if self.truncate == 1:
            r_r = r_r >> truncate_bits
            r_i = r_i >> truncate_bits
        else: 
        # rounding by adding 0.5 plus random bit to prevent bias
            biasCorrectionString = "0b0"
            for i in range(truncate_bits-1):
                biasCorrectionString += "1"
            if (rounding_cy == 1):
                biasCorrectionString += "1"
            else:
                biasCorrectionString += "0"
            biasCorrectionNumber = FixedPoint(biasCorrectionString, signed=False,m=truncate_bits+1,n=0)
            r_r = (r_r + biasCorrectionNumber) >> truncate_bits
            r_i = (r_i + biasCorrectionNumber) >> truncate_bits
        
        
        r_r = int(FixedPoint(r_r,m=self.output_width//2,signed=signFlag,overflow_alert='ignore',overflow='wrap'))
        r_i = int(FixedPoint(r_i,m=self.output_width//2,signed=signFlag,overflow_alert='ignore'))
        r_bytes = r_r.to_bytes(byteorder=byteOrder,length=self.output_width//8//2,signed=signFlag)
        i_bytes = r_i.to_bytes(byteorder=byteOrder,length=self.output_width//8//2,signed=signFlag)
        result = bytearray(i_bytes)
        result += r_bytes
        # print("(%i + j%i) * (%i + j%i) = (%i + j%i)"%(a_r,a_i,b_r,b_i,r_r,r_i))
        # print("(%s) * (%s) = %s"%(a.hex(),b.hex(),result.hex()))
        return result