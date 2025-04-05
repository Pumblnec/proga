# Раздел №2
input_string = input("Введите строку: ")

original_length = len(input_string)
modified_string = input_string.replace('a', '').replace('A', '')
new_length = len(modified_string)

print("Строка после удаления букв 'а':", modified_string)
print("Количество удалённых символов:", original_length - new_length)