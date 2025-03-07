import os
import re
from github import Github
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def convert_ms(ms, offset=0):
    """精确时间转换（含偏移）"""
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
    """最终修复版本（保留空格+正确偏移）"""
    spl_lines = []
    
    # 增强正则表达式（精确匹配所有字符）
    line_pattern = re.compile(r'\[(\d+)\](.*?)(?=\[\d+\]|$)', re.DOTALL)
    word_pattern = re.compile(r'([^\n\(\)]*?)\s*\((\d+),(\d+)\)')
    
    for line in lys_text.split('\n'):
        line = line.strip()
        if not line.startswith('['):
            continue
            
        # 解析歌词行
        content_match = line_pattern.match(line)
        if not content_match:
            continue
            
        content = content_match.group(2)
        word_entries = word_pattern.findall(content)
        
        if not word_entries:
            continue

        segments = []
        last_end = 0
        for idx, (raw_word, s, d) in enumerate(word_entries):
            # 应用偏移到所有时间参数
            original_start = int()
            start = original_start + time_offset
            duration = int(d)
            end = start + duration  # 结束时间需要包含偏移
            
            # 保留原始空格（关键修改）
            word = raw_word.rstrip('\r\n')
            
            # 生成时间戳
            start_time = convert_ms(original_start, time_offset)
            segments.append(f"[{start_time}]{word}")
            
            # 处理间隔时间戳
            if idx < len(word_entries)-1:
                next_start = int(word_entries[idx+1][1]) + time_offset
                if end < next_start:
                    segments.append(f"[{convert_ms(end)}]")
            
            last_end = end
        
        # 添加行尾时间戳
        if segments:
            segments.append(f"[{convert_ms(last_end)}]")
            spl_lines.append(''.join(segments))
    
    return '\n'.join(spl_lines)

def main():
    token = os.getenv('GITHUB_TOKEN')
    issue_number = int(os.getenv('ISSUE_NUMBER'))
    repo_name = os.getenv('GITHUB_REPOSITORY')

    if not all([token, issue_number, repo_name]):
        logger.error("缺少环境变量")
        return

    try:
        g = Github(token)
        repo = g.get_repo(repo_name)
        issue = repo.get_issue(number=issue_number)
        
        offset, lys_content = parse_issue_content(issue.body)
        logger.info(f"解析到偏移量: {offset}，歌词内容长度: {len(lys_content)}")
        
        if not lys_content:
            issue.create_comment("错误：未找到有效的LYS歌词内容")
            return

        try:
            spl_output = lys_to_spl(lys_content, offset)
            logger.info("转换结果验证:\n" + "\n".join(spl_output.split('\n')[:3]))
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
