#!/bin/bash

echo "🚀 [1/2] 正在通过文件系统获取 openapi.json..."

# 核心逻辑：利用 WSL2 可以直接访问 Windows localhost 的特性
# 注意：在较新版本的 WSL2 中，可以直接用 localhost 访问 Windows 服务
# 如果 localhost 不行，再换回那个 IP 地址
curl -f http://localhost:8000/openapi.json -o ./openapi.json

if [ $? -ne 0 ]; then
    echo "❌ 错误：无法连接到后端 (http://localhost:8000)"
    echo "请检查后端服务是否启动，或者防火墙是否拦截。"
    exit 1
fi

echo "✅ 下载成功！文件大小："
ls -lh ./openapi.json | awk '{print $5}'

echo "⚙️ [2/2] 正在生成 TypeScript 代码..."
npx openapi-ts

echo "🎉 全部完成！"