# Use the generator file to generate the project files

```
python generate-swagger-studio-v9-2.py
``

Or Use the older version of the project

# Install Dependencies

```
pip install -r requirements.txt
```

# How to run

```
python app.py
```

# Accessible From
http://127.0.0.1:5000


# Publishing in PODMAN(DOCKER)

* Open wsl

```
wsl
```

* Create a directory in wsl

```
mkdir -p ~/projects/swagger-studio
```

* Copy from windows to wsl directory
```
cp -r /mnt/c/Karthick/VSCODE/KKAI/swagger-gui-editor-v9/* .
```

* update the below line in the app.py file

from
```
app.run(debug=True)
```
to
```
app.run(host="0.0.0.0", port=5000, debug=True)
```

* create Docker file inside the ~/projects/swagger-studio

```
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1

EXPOSE 5000

CMD ["python", "app.py"]
```

* create .containerignore file inside ~/projects/swagger-studio

```
__pycache__/
*.pyc
*.pyo
*.pyd
.venv/
venv/
.git/
.gitignore
swagger_specs.db
```
* create .dockerignore file inside ~/projects/swagger-studio

```
cp .containerignore .dockerignore
```

* build the podman image

```
cd ~/projects/swagger-studio
podman build -t swagger-studio .
```

* run the image

```
podman run --replace -d --name swagger-studio-app -p 5000:5000 swagger-studio
```

hostname -I
