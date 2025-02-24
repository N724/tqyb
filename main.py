import aiohttp
import json
import logging
from typing import Optional
from aistrbot.api.all import AstrMessageEvent, CommandResult, Context, Plain
import aistrbot.api.event.filter as filter
from aistrbot.api.star import register, Star

logger = logging.getLogger("astrbot")

WEATHER_SOURCES = {
    "moji": "墨迹天气",
    "baidu": "百度天气",
    "zgtq": "中国天气",
    "zytq": "中央天气",
    "cytq": "彩云天气"
}

@register("multi_weather", "Soulter", "多源天气查询", "2.0.0")
class MultiWeather(Star):
    def __init__(self, context: Context) -> None:
        super().__init__(context)
        self.api_url = "https://xiaoapi.cn/API/zs_tq.php"
        self.timeout = aiohttp.ClientTimeout(total=15)

    async def fetch_weather(self, params: dict) -> Optional[dict]:
        """获取天气数据（带智能重试机制）"""
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(self.api_url, params=params) as resp:
                    raw_text = await resp.text()
                    logger.debug(f"Weather API Response: {raw_text[:200]}...")
                    
                    if resp.status != 200:
                        logger.error(f"HTTP Error: {resp.status}")
                        return None
                    
                    try:
                        return json.loads(raw_text)
                    except json.JSONDecodeError:
                        logger.error("Invalid JSON Response")
                        return {"code": 201, "msg": "数据解析失败"}

        except aiohttp.ClientError as e:
            logger.error(f"Network Error: {str(e)}")
            return {"code": 201, "msg": "网络连接异常"}
        except Exception as e:
            logger.error(f"Unexpected Error: {str(e)}", exc_info=True)
            return {"code": 201, "msg": "服务器开小差了"}

    @filter.command("天气")
    async def query_weather(self, event: AstrMessageEvent):
        '''[城市名] [来源] - 查询多版本天气（来源可选：moji/baidu/zgtq/zytq/cytq）'''
        args = event.get_plain_args().split()
        
        # 🍃 参数验证
        if len(args) < 1:
            yield CommandResult().message("🌸 使用示例：天气 北京 cytq\n🌿 支持来源：" + "/".join(WEATHER_SOURCES.values()))
            return

        city = args[0]
        source_type = args[1].lower() if len(args)>=2 else "cytq"
        
        # 🍄 校验天气源类型
        if source_type not in WEATHER_SOURCES:
            yield CommandResult().error(f"🚫 不支持的天气源哦～可用来源：{'/'.join(WEATHER_SOURCES.keys())}")
            return

        # 🌈 构建请求参数
        params = {
            "type": source_type,
            "msg": city,
            "n": "1"  # 默认返回详情
        }
        if len(args) >=3 and args[2].isdigit():
            params["num"] = args[2]

        # 🚀 发送请求
        yield CommandResult().message(f"🌤️ 正在召唤{WEATHER_SOURCES[source_type]}...")
        
        data = await self.fetch_weather(params)
        if not data or data.get("code") != 200:
            error_msg = data.get("msg", "未知错误") if data else "请求失败"
            yield CommandResult().error(f"🌩️ 天气获取失败：{error_msg}")
            return

        # 🎨 格式化消息
        weather_info = [
            f"📍 {data.get('name', '未知地区')}",
            "🌐 数据来源：" + WEATHER_SOURCES.get(source_type, "未知")
        ]

        # ✨ 解析天气数据
        if data.get("data"):
            weather_info.extend(["🌡️ " + line for line in data["data"].split("\n") if line])
        
        # 🌸 生活指数（仅中国天气）
        if source_type == "zgtq" and data.get("shzs"):
            weather_info.append("\n🌈 生活指数：")
            weather_info.extend(["💡 " + line for line in data["shzs"].split("\n") if line])

        # 🍃 添加小提示
        weather_info.append(f"\n📌 {data.get('tips', '')}")

        yield CommandResult().message("\n".join(weather_info)).use_t2i(False)

    @filter.command("天气帮助")
    async def weather_help(self, event: AstrMessageEvent):
        '''获取天气查询帮助'''
        help_msg = [
            "🌦️【多源天气查询指南】",
            "指令格式：天气 [城市] [来源]",
            "🌐 可用天气源：",
            "\n".join([f"• {k} ({v})" for k,v in WEATHER_SOURCES.items()]),
            "📝 示例：",
            "天气 北京         → 默认使用彩云天气",
            "天气 上海 moji    → 墨迹天气数据",
            "天气 广州 zgtq 10 → 获取前10条中国天气数据",
            "🍃 数据更新可能有延迟，请以实际情况为准～"
        ]
        yield CommandResult().message("\n".join(help_msg))
