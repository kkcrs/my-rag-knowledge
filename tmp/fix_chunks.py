import sys
with open(sys.argv[1], 'r') as f:
    content = f.read()

old = '''    async def list_chunks(
        self,
        document_id: UUID,
        page: int,
        page_size: int,
    ) -> tuple[list[DocumentChunk], int, ChunkStats | None]:
        # 先确保 document 存在，否则空文档与"文档不存在"会混在一起
        await self.get(document_id, permission_tags=permission_tags)'''

new = '''    async def list_chunks(
        self,
        document_id: UUID,
        page: int,
        page_size: int,
        *,
        permission_tags: list[str] | None = None,
    ) -> tuple[list[DocumentChunk], int, ChunkStats | None]:
        # 先确保 document 存在，否则空文档与"文档不存在"会混在一起
        await self.get(document_id, permission_tags=permission_tags)'''

if old in content:
    content = content.replace(old, new)
    with open(sys.argv[1], 'w') as f:
        f.write(content)
    print('fixed')
else:
    print('not found')
