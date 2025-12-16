FROM python:3.11-slim

WORKDIR /app

# 安装所有系统依赖（一次性搞定）
# - GIS库: gdal, geos, proj, expat (rasterio, fiona, shapely, geopandas, pyproj)
# - 音频库: libsndfile (soundfile)
# - 数学库: openblas (scipy)
# - 数据库: libpq (asyncpg, psycopg)
# - 加密库: libffi, openssl (cryptography)
# - 编译工具: gcc, g++ (grpcio等需要编译的包)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    libexpat1 \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    libsndfile1 \
    libopenblas-dev \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制项目代码
COPY . .

# 暴露端口
EXPOSE 8001

# 启动命令
CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8001"]
