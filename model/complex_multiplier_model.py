from fixedpoint import FixedPoint

class Model:
    def __init__(self, input_width_a, input_width_b, output_width):
        self.input_width_a = input_width_a
        self.input_width_b = input_width_b
        self.output_width = output_width

    def calculate(self, a, b):
        signFlag = True
        a_i = FixedPoint(int.from_bytes(a[0:int(len(a)/2)], byteorder='big',signed=signFlag), signed=signFlag,m=self.input_width_a/2)
        a_r = FixedPoint(int.from_bytes(a[int(len(a)/2):len(a)], byteorder='big',signed=signFlag), signed=signFlag,m=self.input_width_a/2)
        b_i = FixedPoint(int.from_bytes(b[0:int(len(b)/2)], byteorder='big',signed=signFlag), signed=signFlag,m=self.input_width_b/2)
        b_r = FixedPoint(int.from_bytes(b[int(len(b)/2):len(b)], byteorder='big',signed=signFlag), signed=signFlag,m=self.input_width_b/2)
        r_r = int(a_r*b_r) - int(a_i*b_i)
        r_i = int(a_r*b_i) + int(a_i*b_r)
        # truncate
        truncate_bits = self.input_width_a + self.input_width_b - self.output_width
        #r_r = r_r >> truncate_bits
        #r_i = r_i >> truncate_bits
        r_r = int(FixedPoint(r_r,m=int(self.output_width/2),signed=signFlag,overflow_alert='ignore',overflow='wrap'))
        r_i = int(FixedPoint(r_i,m=int(self.output_width/2),signed=signFlag,overflow_alert='ignore'))
        r_bytes = r_r.to_bytes(byteorder='big',length=int(self.output_width/8/2),signed=signFlag)
        i_bytes = r_i.to_bytes(byteorder='big',length=int(self.output_width/8/2),signed=signFlag)
        result = bytearray(i_bytes)
        result += r_bytes
        #print("(%i + j%i) * (%i + j%i) = (%i + j%i)"%(a_r,a_i,b_r,b_i,r_r,r_i))
        #print("(%s) * (%s) = %s"%(a.hex(),b.hex(),result.hex()))
        return result