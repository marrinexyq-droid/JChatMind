package com.marrine.jchatmind.mapper;

import com.marrine.jchatmind.model.entity.ChatMessage;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

/**
 * @author charon
 * @description 针对表【chat_message】的数据库操作Mapper
 * @createDate 2025-12-02 15:40:13
 * @Entity com.marrine.jchatmind.model.entity.ChatMessage
 */
@Mapper
public interface ChatMessageMapper {
    int insert(ChatMessage chatMessage);

    ChatMessage selectById(String id);

    List<ChatMessage> selectBySessionId(String sessionId);

    List<ChatMessage> selectBySessionIdRecently(String sessionId, int limit);

    int deleteById(String id);

    int updateById(ChatMessage chatMessage);

    /** 原子追加内容，避免 read-modify-write 竞态 */
    int appendContent(@Param("id") String id, @Param("appendContent") String appendContent);
}
