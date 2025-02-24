import aiohttp
import logging
from typing import Optional
from astrbot.api.all import AstrMessageEvent, CommandResult, Context, Plain
import astrbot.api.event.filter as filter
from astrbot.api.star import register, Star

logger = logging.getLogger("astrbot")

@register("weather", "作者名", "多源天气查询插件", "1.0.0")
class WeatherPlugin(Star):
    def __init__(self, context: Context) -> None:
        super().__init__(context)
        self.api_url = "https://xiaoapi.cn/API/zs_tq.php"
        self.timeout = aiohttp.ClientTimeout(total=15)
        self.source_map = {
            "baidu": "百度天气",
            "moji": "墨迹天气",
            "zgtq": "中国天气",
            "zytq": "中央天气",
            "cytq": "彩云天气"
        }

    async def fetch_weather(self, params: dict) -> Optional[dict]:
        """获取天气数据（增强错误处理）"""
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(self.api_url, params=params) as resp:
                    raw_text = await resp.text()
                    logger.debug(f"API原始响应: {raw_text[:200]}...")

                    if resp.status != 200:
                        logger.error(f"HTTP错误: {resp.status}")
                        return None
                    
                    try:
                        return await resp.json()
                    except Exception as e:
                        logger.error(f"JSON解析失败: {str(e)}")
                        return None

        except aiohttp.ClientError as e:
            logger.error(f"网络请求异常: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"未知异常: {str(e)}", exc_info=True)
            return None

    @filter.command("weather")
    async def weather_query(self, event: AstrMessageEvent):
        '''天气查询指令'''
        try:
            # 发送等待提示
            yield CommandResult().message("🌤 正在获取天气数据...")

            # 解析参数
            args = event.message_str.split()[1:]
            if len(args) < 1:
                yield CommandResult().error("❌ 格式错误\n正确格式：/weather [地区] [来源]\n示例：/weather 北京 moji")
                return
            
            location = args[0]
            source_type = "baidu"
            if len(args) >= 2 and args[1] in self.source_map:
                source_type = args[1]

            # 构建请求参数
            params = {
                "type": source_type,
                "msg": location,
                "n": "1"
            }

            # 获取数据
            data = await self.fetch_weather(params)
            if not data:
                yield CommandResult().error("🌩 天气数据获取失败，请稍后重试")
                return

            # 处理响应
            if data.get("code") != 200:
                logger.error(f"API错误: {data.get('code')}")
                yield CommandResult().error(f"⛈ 查询失败：{data.get('msg', '未知错误')}")
                return

            # 构建消息
            msg = [
                f"🌤 {self.source_map[source_type]} - {data.get('name', '未知地区')}",
                "➖" * 15
            ]

            if "data" in data:
                weather_data = data["data"].split("\n")
                for line in weather_data:
                    if "：" in line:
                        key, value = line.split("：", 1)
                        msg.append(f"▫️ {key}: {value.strip()}")

            if source_type == "zgtq" and "shzs" in data:
                msg.append("\n📊 生活指数：")
                msg.append(data["shzs"].replace("\n", " | "))

            yield CommandResult().message("\n".join(msg)).use_t2i(False)

        except Exception as e:
            logger.error(f"处理指令异常: {str(e)}", exc_info=True)
            yield CommandResult().error("🌪 天气查询服务暂时不可用")

    @filter.command("weather_sources")
    async def list_sources(self, event: AstrMessageEvent):
        """查看支持的天气源"""
        sources = ["🔹 可用天气源："]
        sources.extend([f"{name} ({key})" for key, name in self.source_map.items()])
        yield CommandResult().message("\n".join(sources))
