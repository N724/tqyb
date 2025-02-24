import aiohttp
import re
import logging
import time
from typing import Optional
from astrbot.api.all import AstrMessageEvent, CommandResult, Context, Plain
import astrbot.api.event.filter as filter
from astrbot.api.star import register, Star

logger = logging.getLogger("astrbot")

@register("weather_report", "nbx", "精准天气查询插件", "1.1.0")
class WeatherStar(Star):
    def __init__(self, context: Context) -> None:
        super().__init__(context)
        # 主备双API配置
        self.main_api = "https://xiaoapi.cn/API/tq.php"
        self.backup_api = "https://api.weather.backup/v3"
        self.timeout = aiohttp.ClientTimeout(total=10)
        self.headers = {
            "User-Agent": "AstrBotWeather/1.0",
            "From": "astrbot@service.com"
        }
        self.retry_count = 2
        self.cache = {}

    async def _fetch_data(self, location: str) -> Optional[str]:
        """带重试机制的请求核心方法"""
        params = {"msg": location}
        for attempt in range(self.retry_count + 1):
            try:
                async with aiohttp.ClientSession(headers=self.headers, timeout=self.timeout) as session:
                    async with session.get(self.main_api, params=params) as resp:
                        if resp.status == 200:
                            data = await resp.text(encoding='utf-8')
                            self.cache[location] = (time.time(), data)
                            return data
                        logger.warning(f"主API异常 HTTP {resp.status} 第{attempt+1}次重试")
            except aiohttp.ClientError as e:
                if attempt >= self.retry_count:
                    logger.error(f"主API请求失败: {str(e)}")
                    return await self._try_backup_api(location)
                logger.warning(f"网络波动 第{attempt+1}次重试")
        return None

    async def _try_backup_api(self, location: str) -> Optional[str]:
        """备用API请求"""
        try:
            async with aiohttp.ClientSession(headers=self.headers) as session:
                async with session.get(self.backup_api, params={"q": location}) as resp:
                    if resp.status == 200:
                        return await resp.text()
                    logger.error(f"备用API异常 HTTP {resp.status}")
        except Exception as e:
            logger.error(f"备用API失败: {str(e)}")
        return None

    def _parse_weather(self, raw_data: str) -> dict:
        """多级数据解析引擎"""
        result = {
            "location": "未知地区",
            "temp": "N/A", 
            "feel_temp": "N/A",
            "humidity": "N/A",
            "warnings": [],
            "rains": []
        }
        
        # 第一层解析：基础信息
        base_info = re.search(
            r"^(.*?)\n温度：(\d+)℃\n体感：([\d.]+)℃\n湿度：(\d+)%", 
            raw_data
        )
        if base_info:
            result.update({
                "location": base_info.group(1),
                "temp": f"{base_info.group(2)}℃",
                "feel_temp": f"{base_info.group(3)}℃",
                "humidity": f"{base_info.group(4)}%"
            })
        
        # 第二层解析：预警信息
        warnings = re.findall(
            r"【预警中】(.*?（数据来源：.*?）)", 
            raw_data
        )
        result["warnings"] = [f"⚠️ {w}" for w in warnings]
        
        # 第三层解析：降雨提示
        if rain_info := re.search(r"您(.*?)正在下(.*?)，", raw_data):
            result["rains"].append(f"🌧️ {rain_info.group(1)}正在{rain_info.group(2)}")
        
        return result

    def _build_message(self, data: dict) -> str:
        """构建微信友好消息"""
        msg = [f"🌏【{data['location']}天气速报】"]
        
        # 核心信息区块
        msg.extend([
            f"🌡️ 温度：{data['temp']}（体感{data['feel_temp']}）",
            f"💧 湿度：{data['humidity']}",
            ""
        ])
        
        # 预警信息处理
        if data["warnings"]:
            msg.append("🚨 气象预警：")
            msg.extend(data["warnings"])
            msg.append("")
        
        # 降雨信息处理
        if data["rains"]:
            msg.append("🌧️ 降水提醒：")
            msg.extend(data["rains"])
            msg.append("")
        
        # 尾部信息
        msg.extend([
            "📡 数据来源：中国气象局",
            "🔍 输入【天气帮助】获取使用指南"
        ])
        
        return "\n".join(msg)

    @filter.command("天气", "查天气")
    async def get_weather(self, event: AstrMessageEvent):
        '''查询实时天气 例：天气 上海浦东'''
        try:
            # 参数验证
            if not event.args:
                yield CommandResult().error("📍 请提供查询地址（例：天气 北京朝阳区）")
                return
                
            location = " ".join(event.args)
            
            # 发送等待提示
            yield CommandResult().message(f"⛅ 正在卫星定位【{location}】...")
            
            # 检查缓存（5分钟有效期）
            if cached := self.cache.get(location):
                if time.time() - cached < 300:
                    data = self._parse_weather(cached)
                    yield CommandResult().message(self._build_message(data))
                    return
            
            # 获取数据
            if raw_data := await self._fetch_data(location):
                weather_data = self._parse_weather(raw_data)
                response = self._build_message(weather_data)
                yield CommandResult().message(response).use_t2i(False)
            else:
                yield CommandResult().error(self._get_error_help())
                
        except Exception as e:
            logger.error(f"指令处理失败: {str(e)}", exc_info=True)
            yield CommandResult().error("🌩️ 天气雷达信号丢失，请稍后重试")

    @filter.command("天气帮助")
    async def show_help(self, event: AstrMessageEvent):
        """获取使用帮助"""
        help_msg = (
            "🌦️ 天气查询帮助 🌦️\n\n"
            "1. 基础查询：\n"
            "   » 天气 北京朝阳\n"
            "   » 查天气 上海陆家嘴\n\n"
            "2. 高级功能：\n"
            "   » 输入【天气预警】获取最新预警\n"
            "   » 输入【网络诊断】检查服务状态\n\n"
            "3. 故障排除：\n"
            "   • 地址不要带'市/区'后缀\n"
            "   • 遇到错误请截屏反馈"
        )
        yield CommandResult().message(help_msg)

    @filter.command("网络诊断")
    async def network_check(self, event: AstrMessageEvent):
        """检测服务连通性"""
        test_points = [
            ("主天气API", self.main_api),
            ("备用天气API", self.backup_api),
            ("百度服务", "https://www.baidu.com")
        ]
        
        results = []
        for name, url in test_points:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=8) as resp:
                        status = "🟢 正常" if resp.status == 200 else f"🔴 异常({resp.status})"
            except Exception as e:
                status = f"🔴 故障({str(e)[:20]})"
            results.append(f"{name}: {status}")
        
        report = (
            "📡 服务状态诊断报告\n\n"
            + "\n".join(results) +
            "\n\n🔧 自助修复建议：\n"
            "1. 检查设备网络连接\n"
            "2. 尝试切换WIFI/移动数据\n"
            "3. 联系管理员获取帮助"
        )
        yield CommandResult().message(report)

    def _get_error_help(self) -> str:
        """生成带解决方案的错误提示"""
        return (
            "⚠️ 服务暂时不可用\n\n"
            "可能原因：\n"
            "1. 网络连接不稳定\n"
            "2. 查询地址不准确\n"
            "3. 气象服务维护\n\n"
            "建议操作：\n"
            "• 检查输入地址格式\n"
            "• 使用【网络诊断】功能\n"
            "• 稍后重新尝试查询"
        )
