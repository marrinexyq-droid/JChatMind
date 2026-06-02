package com.kama.jchatmind.model.vo;

import java.util.List;

public record RerankRequest(String query, List<String> documents) {
}
