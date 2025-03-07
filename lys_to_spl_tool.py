import os
import re
from github import Github
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def convert_ms(ms, offset=0):
    """精确处理时间偏移和负数"""
    adjusted = int(ms) + offset
    adjusted = max(adjusted, 0)  # 防止负时间
    minutes, ms = divmod(adjusted, 60000)
    seconds, milliseconds = divmod(ms, 1000)
    return f"{minutes:02d}:{seconds:02d}.{milliseconds:03d}"

def parse_issue_content(content):
    """增强型Issue内容解析"""
    try:
        # 使用更健壮的正则表达式
        offset_match = re.search(r'### offset\s+([\d-]+)', content, re.IGNORECASE)
        lys_match = re.search(r'### LYS 歌词\s+((?:\[.*?\]\s*.*?\n?)+)', content, re.IGNORECASE|re.DOTALL)
        
        offset = int(offset_match.group(1).strip()) if offset_match else 0
        lys_content = lys_match.group(1).strip() if lys_match else ''
        return offset, lys_content
    except Exception as e:
        logger.error(f"内容解析失败: {str(e)}")
        return 0, ''
        
def lys_to_spl(lys_text, time_offset=0):
    """完整保留括号的最终版本"""
    spl_lines = []
    
    # 增强正则表达式（支持嵌套括号）
    word_pattern = re.compile(r'''
        (.*?)                # 非贪婪匹配所有字符
        \s*                  # 吸收空白
        \((\d+),(\d+)\)      # 时间参数
    ''', re.VERBOSE|re.DOTALL)
    
    for line in lys_text.split('\n'):
        line = line.strip()
        if not line.startswith('['):
            continue

        # 分离属性和歌词内容
        prop_match = re.match(r'\[(\d+)\](.*)', line)
        if not prop_match:
            continue
            
        prop, content = prop_match.groups()
        word_entries = word_pattern.findall(content)
        
        if not word_entries:
            continue

        spl_segments = []
        last_end = 0
        
        for idx, (word, start_str, duration_str) in enumerate(word_entries):
            # 应用时间偏移
            original_start = int(start_str)
            start = original_start + time_offset
            duration = int(duration_str)
            end = original_start + duration + time_offset
            
            # 完整保留原始格式（含空格和括号）
            cleaned_word = word.replace('\n', ' ').replace('\r', '').rstrip()
            if word.endswith(' '):  # 保留结尾空格
                cleaned_word += ' '
            
            # 添加起始时间戳和单词
            spl_segments.append(f"[{convert_ms(start)}]{cleaned_word}")
            
            # 检测间隔并添加结束标记
            if idx < len(word_entries)-1:
                next_start = int(word_entries[idx+1][1]) + time_offset
                if end < next_start:
                    spl_segments.append(f"[{convert_ms(end)}]")
            
            last_end = end
        
        # 添加行尾结束标记
        if spl_segments:
            spl_line = "".join(spl_segments) + f"[{convert_ms(last_end)}]"
            spl_lines.append(spl_line)
    
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
            comment.append("**LYS 输出:**\n```\n" + spl_output + "\n```")
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
