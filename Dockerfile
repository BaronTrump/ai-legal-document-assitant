FROM python:3.11-slim
WORKDIR /app
RUN pip install flask python-dotenv openai requests gunicorn
COPY APIs/ APIs/
COPY Templates/ Templates/
COPY WebApp/ WebApp/
EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "WebApp.app:app"]
