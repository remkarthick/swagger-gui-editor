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

If you've built a new image and want the container to use the updated image:

```
cd ~/projects/swagger-studio
podman build -t swagger-studio .
podman run --replace -d --name swagger-studio-app -p 5000:5000 swagger-studio
```

* Start the existing container

Use this command to start the swagger-studio-app container if it has already been created and is currently stopped. This avoids recreating the container and preserves any existing configuration and data associated with it.

```
podman start swagger-studio-app
```

* Stop the container

Use this command to gracefully stop the running swagger-studio-app container. The container and its data are retained, allowing it to be started again later when needed.

```
podman stop swagger-studio-app
```

# Accessing Swagger Studio

Swagger Studio runs inside a Podman container hosted on WSL and is exposed on port 5000. Because the application is running within WSL, you must use the WSL instance's IP address to access it from your browser.

1. Find the WSL IP Address

Open a WSL terminal and run:

hostname -I

Example output:

172.27.45.123

Use the first IP address returned by the command.

2. Access Swagger Studio

Open a browser and navigate to:

http://<WSL_IP_ADDRESS>:5000

For example:

http://172.27.45.123:5000
