fg_table = []
        #first bit
addr = 1
bit = 0
node_id = 32
number_of_bits = 10

        #for loop that iterates over the first new table creating entries
while bit != number_of_bits:
    x = node_id + 2**bit
    fg_table.append([x,addr]);
    #new_entry
    bit = bit + 1 

print(fg_table)
