#!/bin/sh

# 使用环境变量
MYSQL_HOST=${MYSQL_HOST:-mysql}
MYSQL_PORT=${MYSQL_PORT:-3306}
MYSQL_USER=${MYSQL_USER:-root}
MYSQL_PASSWORD=${MYSQL_PASSWORD:-sdkjfhsdkjhfsdkhfksd}
REDIS_HOST=${REDIS_HOST:-redis}
REDIS_PORT=${REDIS_PORT:-6379}

until mysqladmin ping -h "$MYSQL_HOST" -P "$MYSQL_PORT" -u "$MYSQL_USER" -p"$MYSQL_PASSWORD" --silent; do
    echo "Waiting for MySQL to be available..."
    sleep 1
done

until redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping; do
    echo "Waiting for Redis to be available..."
    sleep 1
done

echo "All dependencies are ready!"
exec "$@"