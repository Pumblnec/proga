from flask import Flask, request, jsonify
import random
import json

app = Flask(__name__)


# 1. GET /number/
@app.route('/number/', methods=['GET'])
def get_number():
    param = float(request.args.get('param'))
    random_num = random.uniform(0, 100)
    result = random_num * param
    return jsonify({"result": result})


# 2. POST /number/
@app.route('/number/', methods=['POST'])
def post_number():
    data = request.get_json()
    json_param = float(data['jsonParam'])
    random_num = random.uniform(0, 100)
    operation = random.choice(["+", "-", "*", "/"])

    if operation == "+":
        result = random_num + json_param
    elif operation == "-":
        result = random_num - json_param
    elif operation == "*":
        result = random_num * json_param
    elif operation == "/":
        if json_param == 0:
            return jsonify({"error": "Division by zero!"}), 400
        result = random_num / json_param

    return jsonify({
        "random_number": random_num,
        "operation": operation,
        "result": result
    })


# 3. DELETE /number/
@app.route('/number/', methods=['DELETE'])
def delete_number():
    random_num = random.uniform(0, 100)
    operation = random.choice(["+", "-", "*", "/"])
    return jsonify({
        "random_number": random_num,
        "operation": operation
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)