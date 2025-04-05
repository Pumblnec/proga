import sys

# Задание 1.1.1.

number1 = float(sys.stdin.readline().strip())
number2 = float(sys.stdin.readline().strip())
number3 = float(sys.stdin.readline().strip())

minimal_number = min(number1, number2, number3)

print(f'Минимальное число: {minimal_number}')


# Задание 1.1.2.

number4 = float(sys.stdin.readline().strip())
number5 = float(sys.stdin.readline().strip())
number6 = float(sys.stdin.readline().strip())

numbers_massive = [number4, number5, number6]
for number in numbers_massive :
    if 1 <= number <= 50:
        print(f'Число в интервале [1;50]: {number}')
    else:
        print(f'Число не попадает в интервал [1;50]: {number}')


# Задание 1.1.3.

m = float(sys.stdin.readline().strip())

for i in range (1, 11):
    print(f'{i} * {m} = {i * m}')


# Задание 1.1.4.

data_input = sys.stdin.readline().strip()

numbers = []
current_number = ''
for char in data_input:
    if char == ' ':
        if current_number:
            numbers.append(int(current_number))
            current_number = ''
    else:
        current_number += char
if current_number:
    numbers.append(int(current_number))

sum = 0
count = 0

i = 0
while i < len(numbers):
    sum += numbers[i]
    count += 1
    i += 1

print(f"Сумма всех чисел: {sum}")
print(f"Количество всех чисел: {count}")