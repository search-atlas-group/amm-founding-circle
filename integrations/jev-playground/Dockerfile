FROM python:3.12-slim

WORKDIR /app
COPY . .

# Stdlib-only server, no pip install needed.
EXPOSE 8765
ENV PORT=8765

# TYPESAFE_API_KEY is supplied at `docker run` time (-e or --env-file).
# --no-key-prompt: containers have no interactive TTY for getpass.
# --host 0.0.0.0: default loopback bind is unreachable through the port mapping.
CMD ["python3", "run.py", "--no-key-prompt", "--host", "0.0.0.0"]
