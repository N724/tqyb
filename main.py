from astrbot.api.all import *
import aiohttp
import re

@register("weather", "作者名", "多源天气查询插件", "1.0.0")
class WeatherPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.api_url = "https://xiaoapi.cn/API/zs_tq.php"
        self.source_map = {
            "baidu": "百度天气",
            "moji": "墨迹天气",
            "zgtq": "中国天气",
            "zytq": "中央天气",
            "cytq": "彩云天气"
        }

    @filter.command("weather")
    async def weather_query(self, event: AstrMessageEvent):
        """
        天气查询指令格式：
        /weather [地区] [来源]
        示例：/weather 北京 baidu
        可用来源：baidu, moji, zgtq, zytq, cytq
        """
        args = event.message_str.split()[1:]
        
        # 解析参数
        if len(args) < 1:
            yield event.plain_result("❌ 请输入查询地区！\n示例：/weather 上海 moji")
            return
        
        location = args[0]
        source_type = "baidu"  # 默认百度天气
        
        if len(args) >= 2 and args[1] in self.source_map:
            source_type = args[1]
        
        try:
            # 构建请求参数
            params = {
                "type": source_type,
                "msg": location,
                "n": "1"
            }
            
            # 发送API请求
            async with aiohttp.ClientSession() as session:
                async with session.get(self.api_url, params=params) as response:
                    data = await response.json()
                    
                    if data["code"] != 200:
                        yield event.plain_result(f"❌ 查询失败，错误码：{data['code']}")
                        return
                    
                    # 格式化响应数据
                    result = [
                        f"🌤 {self.source_map[source_type]} - {data['name']}",
                        "➖" * 15
                    ]
                    
                    # 解析天气数据
                    weather_data = data["data"].split("\n")
                    for line in weather_data:
                        if "：" in line:
                            key, value = line.split("：", 1)
                            result.append(f"▫️ {key}: {value.strip()}")
                    
                    # 添加生活指数（中国天气特有）
                    if source_type == "zgtq" and "shzs" in data:
                        result.append("\n📊 生活指数：")
                        result.append(data["shzs"].replace("\n", " | "))
                    
                    yield event.plain_result("\n".join(result))
                    
        except aiohttp.ClientError:
            yield event.plain_result("❌ 网络请求失败，请稍后重试")
        except Exception as e:
            self.logger.error(f"Weather query error: {str(e)}")
            yield event.plain_result("❌ 天气查询服务暂时不可用")

    @filter.command("weather_sources")
    async def list_sources(self, event: AstrMessageEvent):
        """查看支持的天气源列表"""
        sources = ["🔹 可用天气源："]
        for key, name in self.source_map.items():
            sources.append(f"{name} ({key})")
        yield event.plain_result("\n".join(sources))
