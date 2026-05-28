package com.kama.jchatmind.agent.tools;

import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;

@Slf4j
@Component
public class WeatherTools implements Tool {

    private final WebClient webClient;

    public WeatherTools(WebClient.Builder builder) {
        this.webClient = builder.baseUrl("https://wttr.in").build();
    }

    @Override
    public String getName() {
        return "queryWeather";
    }

    @Override
    public String getDescription() {
        return "查询指定城市的天气信息，包括温度、天气状况、湿度、风速等。";
    }

    @Override
    public ToolType getType() {
        return ToolType.FIXED;
    }

    @org.springframework.ai.tool.annotation.Tool(
            name = "queryWeather",
            description = "查询指定城市的当前天气。参数：city（城市名称，中文或英文，如\"北京\"或\"Beijing\"）。返回温度、天气状况、湿度、风速等信息。" )
    public String queryWeather(String city) {
        if (city == null || city.trim().isEmpty()) {
            return "错误：城市名称不能为空";
        }

        try {
            String response = webClient.get()
                    .uri("/{city}?format=%l:+%c+%t+%h+%w&lang=zh", city.trim())
                    .retrieve()
                    .bodyToMono(String.class)
                    .block();

            if (response == null || response.isBlank()) {
                return "错误：未能获取到 " + city + " 的天气信息";
            }

            log.info("查询天气成功: city={}, result={}", city, response);
            return city + " 的天气：" + response;
        } catch (Exception e) {
            log.error("查询天气失败: city={}", city, e);
            return "错误：查询天气失败 - " + e.getMessage();
        }
    }
}
