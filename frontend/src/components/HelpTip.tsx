import { Info } from '../icons';

const HELP: Record<string, string> = {
  sources:
    '抓取源：聚合的上游 m3u/txt 订阅列表。\n' +
    '配置：新增填 名称 + URL + 类型(m3u/txt)；停用取消勾选 enabled。\n' +
    '运行时按启用的源逐个下载合并。',
  aliases:
    '别名（归一）：把各源乱写的频道名统一成标准名。\n' +
    'canonical=标准名，pattern=匹配式，勾 is_regex 用正则否则子串。\n' +
    '命中即改名，先于模板执行。例：CCTV-1/CCTV1综合 → CCTV1。',
  templates:
    '模板菜单：按标准名决定分组/logo/排序，并筛选收录。\n' +
    'canonical 精确匹配别名后的标准名；group_title 分组，logo 图标，sort 排序权重。\n' +
    '菜单为空=收录全部；未命中项排最后。',
  task:
    '任务：手动触发抓取，看实时日志与阶段。\n' +
    '调度：interval 按小时间隔，time 按每日时刻；时区默认 Asia/Shanghai。\n' +
    '注意：此处改动仅当前进程内存，重启回落 config.yaml。',
  channels:
    '频道：最近一次运行的结果与订阅地址。\n' +
    '复制订阅 URL 到播放器；点频道可在线预览。',
  report:
    '报告：本次运行统计——分辨率分布、分组、源健康、历史。\n' +
    '用于判断源质量与筛选效果，只读。',
};

export default function HelpTip({ id }: { id: string }) {
  const text = HELP[id];
  if (!text) return null;
  return (
    <span className="help-tip" title={text} aria-label={text}>
      <Info />
    </span>
  );
}
