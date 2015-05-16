# this is a utility to create a dictionary data file
# to translate the file names for the image file used
# takes a list of csv files with the image path as the first element,
# and the translated name as the second
# generates another csv file, removing the path

# these parameters should be changed as needed
csv_file_names = ['../Media.csv', '../TuxPaint.csv']
lang = 'ht'

dictionary = {}

for csv_file_name in csv_file_names:
    with open(csv_file_name) as from_file:
        for line in from_file:
            words = line.split(',')
            key = words[0]
            value = words[1]
            # use only from the last "/'
            key = key[key.rfind('/') + 1:].strip()
            value = value[value.rfind('/') + 1:].strip()

            if key not in dictionary:
                dictionary[key] = value

# write to a csv file
with open('./data/%s_dict.csv' % lang, 'w') as dict_file:
    for key in sorted(dictionary):
        dict_file.write('%s,%s\n' % (key, dictionary[key]))
