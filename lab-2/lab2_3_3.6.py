# Раздел №3
import sys

def main():
    if len(sys.argv) < 2:
        print("Ошибка: не указаны элементы массива")
        return

    try:
        arr = list(map(int, sys.argv[1:]))
    except ValueError:
        print("Ошибка: все элементы должны быть целыми числами")
        return

    if not arr:
        print("Ошибка: массив не может быть пустым")
        return

    max_element = max(arr)
    print(f"Максимальный элемент: {max_element}")

    count_less_than_max = len([x for x in arr if x < max_element])
    print(f"Количество элементов меньших максимального: {count_less_than_max}")

    sum_greater_than_5 = sum(x for x in arr if x > 5)
    print(f"Сумма чисел больших 5: {sum_greater_than_5}")


if __name__ == "__main__":
    main()