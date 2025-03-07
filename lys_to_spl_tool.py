import os
import re
from github import Github
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def convert_ms(ms):
    """毫秒转时间戳（自动处理负数）"""
    ms = max(int(ms), 0)  # 确保非负
    minutes, ms = divmod(ms, 60000)
    seconds, milliseconds = divmod(ms, 1000)
    return f"{minutes:02d}:{seconds:02d}.{milliseconds:03d}"

def lys_to_spl(lys_text, offset=0):
    """支持时间偏移的转换核心"""
    spl_lines = []
    
    # 优化后的正则表达式
    word_re = re.compile(r'''
        ([^\n\(]*)          # 捕获组1：歌词文本（允许包含空格）
        \s*                  # 吸收空白
        \((\d+),(\d+)\)      # 捕获组2&3：时间参数
    ''', re.VERBOSE)

    for line in lys_text.split('\n'):
        line = line.strip()
        if not line.startswith('['):
            continue

        # 解析行属性
        prop_match = re.match(r'\[(\d+)\](.*)', line)
        if not prop_match:
            continue
            
        prop, content = prop_match.groups()
        segments = []
        last_end = 0
        
        # 遍历所有单词匹配项
        cursor = 0
        for match in word_re.finditer(content):
            # 获取原始单词和时间
            raw_word = match.group(1)
            raw_start = int(match.group(2))
            raw_duration = int(match.group(3))
            
            # 应用时间偏移
            adjusted_start = raw_start + offset
            adjusted_end = raw_start + raw_duration + offset
            
            # 提取实际单词（保留所有空格）
            actual_word = content[cursor:match.start()].rstrip('\n\r')
            if actual_word:
                raw_word = actual_word + raw_word
            
            # 生成时间戳
            timestamp = convert_ms(adjusted_start)
            segments.append(f"[{timestamp}]{raw_word}")
            last_end = adjusted_end
            cursor = match.end()
        
        if segments:
            end_timestamp = convert_ms(last_end)
            spl_lines.append("".join(segments) + f"[{end_timestamp}]")

    return True, '\n'.join(spl_lines)

def main():
    """GitHub Issue处理主函数"""
    # 从环境变量获取GitHub信息
    token = os.getenv('GITHUB_TOKEN')
    issue_number = int(os.getenv('ISSUE_NUMBER'))
    repo_name = os.getenv('GITHUB_REPOSITORY')

    if not all([token, issue_number, repo_name]):
        logger.error("缺少必要的环境变量")
        return

    try:
        # 初始化GitHub连接
        g = Github(token)
        repo = g.get_repo(repo_name)
        issue = repo.get_issue(number=issue_number)

        # 获取Issue内容
        ttml_content = issue.body
        if not ttml_content:
            issue.create_comment("错误：Issue内容为空")
            return

        # 处理TTML内容
        success, spl_output = lys_to_spl(ttml_content, 150)

        # 构建评论内容
        comment = []
        if success:
            comment.append("**输出:**\n```\n" + spl_output + "\n```")
        else:
            comment.append("正在开发，这是给开发者看的报错信息：处理失败，请检查TTML格式是否正确")

        # 添加评论
        issue.create_comment('\n'.join(comment))
        logger.success("处理结果已提交到Issue")

    except Exception as e:
        logger.exception("正在开发，这是给开发者看的报错信息：GitHub操作失败")
        # 尝试在出现异常时也发布评论，方便调试
        try:
            if 'issue' in locals():
                issue.create_comment(f"正在开发，这是给开发者看的报错信息：处理过程中发生错误: {str(e)}")
        except Exception as inner_e:
            logger.error(f"正在开发，这是给开发者看的报错信息：评论发布失败: {inner_e}")


if __name__ == '__main__':
    main()
    # 移除原文件处理相关代码
