FROM python:3.12-slim
WORKDIR /app
COPY harness ./harness
COPY tests ./tests
COPY DESIGN.md README.md ./
CMD ["sh", "-c", "python3 -m unittest discover -s tests -t . && python3 -m harness dry-run --rule fee"]
