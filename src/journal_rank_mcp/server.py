# MIT License
# Free to use, modify, and distribute. Retain this notice.

from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.types import Tool, TextContent, PromptMessage, GetPromptResult
import mcp.server.stdio

from journal_rank_mcp.database import search_journal, lookup_issn, add_journal
from journal_rank_mcp.fetcher import fetch_journal

server = Server("publication-rank")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="query_journal",
            description="查询学术期刊的等级信息，包括 JCR 分区、中科院分区、影响因子、SJR、H-index 等",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "期刊名称或 ISSN（支持中英文模糊搜索）",
                    },
                    "use_web": {
                        "type": "boolean",
                        "description": "是否从网络获取最新数据（默认 false，仅查询本地数据库）",
                        "default": False,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="list_journals",
            description="列出本地数据库中所有可查的期刊",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="format_citation",
            description="格式化期刊等级信息为文本描述",
            inputSchema={
                "type": "object",
                "properties": {
                    "journal_name": {
                        "type": "string",
                        "description": "期刊名称",
                    },
                    "issn": {
                        "type": "string",
                        "description": "ISSN",
                    },
                    "jcr_quartile": {
                        "type": "string",
                        "description": "JCR 分区，如 Q1",
                    },
                    "jif": {
                        "type": "number",
                        "description": "影响因子",
                    },
                    "cas_zone": {
                        "type": "integer",
                        "description": "中科院分区（大类），如 1, 2, 3, 4",
                    },
                    "cas_sub_zone": {
                        "type": "integer",
                        "description": "中科院小类分区",
                    },
                    "sjr": {
                        "type": "number",
                        "description": "SJR 指标",
                    },
                    "h_index": {
                        "type": "integer",
                        "description": "H-index",
                    },
                },
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "query_journal":
        query = arguments["query"]
        use_web = arguments.get("use_web", False)

        if query.replace("-", "").isdigit() and len(query.replace("-", "")) == 8:
            record = lookup_issn(query)
            if record:
                return [TextContent(type="text", text=_format_journal(record))]

        results = search_journal(query)

        if not results and use_web:
            web_data = await fetch_journal(query)
            if web_data:
                try:
                    add_journal(query, web_data)
                except Exception:
                    pass
                return [TextContent(type="text", text=_format_raw(query, web_data))]

        if not results:
            return [TextContent(type="text", text=f"未找到期刊「{query}」的等级信息。\n提示：启 use_web=true 尝试从网络获取。")]

        parts = [_format_journal(r) + "\n" + "-" * 40 for r in results]
        return [TextContent(type="text", text="\n\n".join(parts))]

    elif name == "list_journals":
        from journal_rank_mcp.database import _load_journals
        journals = _load_journals()
        names = sorted(
            f"{issn}: {entry.get('name', '?')}" for issn, entry in journals.items()
        )
        text = f"本地数据库共 {len(names)} 条期刊记录：\n" + "\n".join(names)
        return [TextContent(type="text", text=text)]

    elif name == "format_citation":
        a = arguments
        lines = [
            f"期刊：{a.get('journal_name', '?')}",
            f"ISSN：{a.get('issn', '?')}",
        ]
        if a.get("jcr_quartile"):
            lines.append(f"JCR分区：{a['jcr_quartile']}")
        if a.get("jif"):
            lines.append(f"影响因子 (JIF)：{a['jif']}")
        if a.get("cas_zone"):
            zone = a["cas_zone"]
            sub = a.get("cas_sub_zone")
            lines.append(f"中科院分区：大类{zone}区" + (f" / 小类{sub}区" if sub else ""))
        if a.get("sjr"):
            lines.append(f"SJR：{a['sjr']}")
        if a.get("h_index"):
            lines.append(f"H-index：{a['h_index']}")
        return [TextContent(type="text", text="\n".join(lines))]

    return [TextContent(type="text", text=f"未知工具: {name}")]


def _format_journal(entry: dict) -> str:
    name = entry.get("name", "?")
    issn = entry.get("issn", entry.get("ISSN", "?"))
    publisher = entry.get("publisher", "")
    lines = [
        f"📘 {name}",
        f"  ISSN: {issn}",
    ]
    if publisher:
        lines.append(f"  出版商: {publisher}")
    if entry.get("jcr_quartile"):
        lines.append(f"  JCR分区: {entry['jcr_quartile']}")
    if entry.get("jif"):
        lines.append(f"  影响因子 (JIF): {entry['jif']}")
    if entry.get("jif_5year"):
        lines.append(f"  5年影响因子: {entry['jif_5year']}")
    if entry.get("wos_category"):
        lines.append(f"  WoS类别: {entry['wos_category']}")
    if entry.get("cas_zone"):
        zone = entry["cas_zone"]
        sub = entry.get("cas_sub_zone")
        if entry.get("cas_top"):
            lines.append(f"  中科院分区: 大类{zone}区 (Top期刊)" + (f" / 小类{sub}区" if sub else ""))
        else:
            lines.append(f"  中科院分区: 大类{zone}区" + (f" / 小类{sub}区" if sub else ""))
    if entry.get("sjr"):
        lines.append(f"  SJR: {entry['sjr']}")
        if entry.get("sjr_quartile"):
            lines.append(f"  SJR分区: {entry['sjr_quartile']}")
    if entry.get("h_index"):
        lines.append(f"  H-index: {entry['h_index']}")
    if entry.get("pkua"):
        lines.append(f"  核心收录: {entry['pkua']}")
    if entry.get("notes"):
        lines.append(f"  备注: {entry['notes']}")
    return "\n".join(lines)


def _format_raw(query: str, data: dict) -> str:
    lines = [f"📘 {query}（网络获取）"]
    if data.get("sjr"):
        lines.append(f"  SJR: {data['sjr']}")
    if data.get("sjr_quartile"):
        lines.append(f"  SJR分区: {data['sjr_quartile']}")
    if data.get("h_index"):
        lines.append(f"  H-index: {data['h_index']}")
    if data.get("categories"):
        lines.append(f"  学科类别: {', '.join(data['categories'])}")
    if data.get("jif"):
        lines.append(f"  影响因子: {data['jif']}")
    if data.get("cas_zone"):
        lines.append(f"  中科院分区: {data['cas_zone']}区")
    if data.get("jcr_quartile"):
        lines.append(f"  JCR分区: {data['jcr_quartile']}")
    return "\n".join(lines)


@server.list_prompts()
async def list_prompts() -> list[type[PromptMessage]]:
    return []


@server.get_prompt()
async def get_prompt(name: str, arguments: dict | None = None) -> GetPromptResult:
    raise ValueError(f"Unknown prompt: {name}")


async def run_server() -> None:
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="publication-rank",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


def main() -> None:
    import asyncio
    asyncio.run(run_server())
