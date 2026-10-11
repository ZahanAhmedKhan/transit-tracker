request: Its a python library that is used to talk to websites

url: variable that holds the address of the website

response: visits the url and asks for information

data: whatever the information is, using .JSON() it gets unpacked into a python dictionary

csv.DicReader: uses the header line as keys and returns one dict per data row

list: Each dict is stored in a list

with: closes the file when the block ends