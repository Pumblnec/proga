import requests
import random

BASE_URL = "http://127.0.0.1:5000"

# 1. GET /number/
param = random.randint(1, 10)
get_response = requests.get(f"{BASE_URL}/number/?param={param}")
get_data = get_response.json()

if "random_number" not in get_data:
    num1 = get_data["result"] / param
    operation1 = "*"
else:
    num1 = get_data["random_number"]
    operation1 = get_data.get("operation", "*")

print(f"GET: {num1} {operation1} {param} = {get_data['result']}")

# 2. POST /number/
json_param = random.randint(1, 10)
post_response = requests.post(
    f"{BASE_URL}/number/",
    json={"jsonParam": json_param},
    headers={"Content-Type": "application/json"}
)
post_data = post_response.json()
num2 = post_data["random_number"]
operation2 = post_data["operation"]

print(f"POST: {num2} {operation2} {json_param} = {post_data['result']}")

# 3. DELETE /number/
delete_response = requests.delete(f"{BASE_URL}/number/")
delete_data = delete_response.json()
num3 = delete_data["random_number"]
operation3 = delete_data["operation"]

print(f"DELETE: {num3} {operation3} ?")

# 4. Составляем выражение: (num1 op1 param) op2 (num2 op3 num3)
expression = f"({num1} {operation1} {param}) {operation2} ({num2} {operation3} {num3})"
result = eval(expression)
final_result = int(round(result))

print("\nИтоговое выражение:", expression)
print("Результат (int):", final_result)

