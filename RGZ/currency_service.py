from flask import Flask, request, jsonify
import logging
from datetime import datetime

app = Flask(__name__)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('currency_service.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

CURRENCY_RATES = {
    'USD': 90.5,
    'EUR': 98.7,
    'CNY': 12.3
}


@app.route('/rate', methods=['GET'])
def get_exchange_rate():
    """Получение курса валюты"""
    currency = request.args.get('currency', '').upper()

    if not currency:
        logger.warning("Запрос без параметра currency")
        return jsonify({"message": "Currency parameter is required"}), 400

    if currency not in CURRENCY_RATES:
        logger.warning(f"Запрошен неизвестный курс: {currency}")
        return jsonify({"message": "UNKNOWN CURRENCY"}), 400

    try:
        rate = CURRENCY_RATES[currency]
        logger.info(f"Успешно возвращен курс {currency}: {rate}")
        return jsonify({
            "currency": currency,
            "rate": rate,
            "timestamp": datetime.now().isoformat()
        }), 200
    except Exception as e:
        logger.error(f"Ошибка при обработке запроса: {str(e)}")
        return jsonify({"message": "UNEXPECTED ERROR"}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)