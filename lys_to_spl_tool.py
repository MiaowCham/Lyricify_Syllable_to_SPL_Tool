import os
import re
from github import Github
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def convert_ms(ms, offset=0):
    """精确时间转换函数"""
    adjusted = int(ms) + offset
    adjusted = max(adjusted, 0)
    minutes, ms = divmod(adjusted, 60000)
    seconds, milliseconds = divmod(ms, 1000)
    return f"{minutes:02d}:{seconds:02d}.{milliseconds:03d}"

def parse_issue_content(content):
    """增强型内容解析"""
    offset_match = re.search(r'^### offset\s*[\r\n]+([-\d]+)', content, re.MULTILINE)
    lys_match = re.search(r'^### LYS 歌词\s*[\r\n]+((?:\[.*?].*?(?:\r?\n|$))+)', content, re.MULTILINE | re.DOTALL)
    
    offset = int(offset_match.group(1)) if offset_match and offset_match.group(1) else 0
    lys_content = lys_match.group(1).strip() if lys_match and lys_match.group(1) else ''
    return offset, lys_content

def lys_to_spl(lys_text, time_offset=0):
    """修复时间轴的核心转换逻辑"""
    spl_lines = []
    # 增强正则表达式：精确匹配歌词行
    line_pattern = re.compile(r'^\[(\d+)\](.*?)(?=\[\d+\]|$)', re.MULTILINE | re.DOTALL)
    # 改进单词匹配：支持括号和特殊字符
    word_pattern = re.compile(r'\s*([^\(\)\n]*?)\s*\((\d+),(\d+)\)')
    
    for line in lys_text.split('\n'):
        line = line.strip()
        if not line.startswith('['):
            continue
            
        # 解析歌词行
        line_match = line_pattern.match(line)
        if not line_match:
            continue
            
        content = line_match.group(2)
        word_entries = word_pattern.findall(content)
        
        if not word_entries:
            continue

        segments = []
        prev_end = 0
        for idx, (word, start_str, dur_str) in enumerate(word_entries):
            # 正确提取时间参数
            original_start = int(start_str)
            start = original_start + time_offset
            duration = int(dur_str)
            end = original_start + duration + time_offset
            
            # 清理单词（保留原始空格）
            clean_word = word.strip('\r\n')
            
            # 添加起始时间戳
            segments.append(f"[{convert_ms(original_start)}]{clean_word}")
            
            # 添加间隔时间戳
            if idx < len(word_entries)-1:
                next_start = int(word_entries[idx+1][1]) + time_offset
                if end < next_start:
                    segments.append(f"[{convert_ms(end)}]")
            prev_end = end
        
        # 添加行尾时间戳
        if segments:
            segments.append(f"[{convert_ms(prev_end)}]")
            spl_lines.append(''.join(segments))
    
    return '\n'.join(spl_lines)

def main():
    token = os.getenv('GITHUB_TOKEN')
    issue_number = int(os.getenv('ISSUE_NUMBER'))
    repo_name = os.getenv('GITHUB_REPOSITORY')

    if not all([token, issue_number, repo_name]):
        logger.error("Missing environment variables")
        return

    try:
        g = Github(token)
        repo = g.get_repo(repo_name)
        issue = repo.get_issue(number=issue_number)
        
        offset, lys_content = parse_issue_content(issue.body)
        logger.info(f"解析到偏移量: {offset}，歌词行数: {len(lys_content.splitlines())}")
        
        if not lys_content:
            issue.create_comment("错误：未找到有效的LYS歌词内容")
            return

        try:
            spl_output = lys_to_spl(lys_content, offset)
            logger.info("转换结果示例:\n" + "\n".join(spl_output.split('\n')[:2]))  # 打印前两行日志
            comment = f"**输出:**\n```\n{spl_output}\n```"
        except Exception as e:
            logger.exception("转换失败")
            comment = f"错误：处理失败 - {str(e)}"

        issue.create_comment(comment)

    except Exception as e:
        logger.exception("主流程异常")
        try:
            issue.create_comment(f"系统错误：{str(e)}")
        except Exception as inner_e:
            logger.error(f"评论失败: {inner_e}")

if __name__ == '__main__':
    main()
