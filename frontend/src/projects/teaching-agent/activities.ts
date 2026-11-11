export const activityIds=['group_books','explain_algorithm','explore_2d'] as const
export type ActivityId=typeof activityIds[number]

export const activities=[
  {id:'group_books' as ActivityId,number:1,title:'和小知一起分组',goal:'选两个开始的中心，看看五本书怎样分成两组。',
    introduction:'这五本书借出去的次数不一样。\n先选两个开始的中心，看看怎样把它们分成两组。',
    pending:'逐轮计算还没有接入，现在不会生成距离、分组或中心答案。',
    guidance:'这一段先体验流程。你可以调整两个开始的中心，或者把想问的问题写下来。真正的一轮计算将在下一段接入。',
    suggestions:['中心点是做什么的？','这一步我想先试试'],topic:'分组计算'},
  {id:'explain_algorithm' as ActivityId,number:2,title:'整理分组的方法',goal:'把刚才的经历整理成四个大步骤。',
    introduction:'刚才，我们已经一起把五本书分好了。\n如果要把这个方法讲给没做过的同学听，你会怎么说？用自己的话讲一讲。\n有哪一步还不明白，也可以直接问我，我们一起想一想。',
    pending:'拖动排序和程序验证还没有接入。这里先展示将要使用的四张步骤卡，不代表你的排序答案。',
    guidance:'这里展示的是四张步骤卡的预览。后面可以拖动排序，并展开看看重复计算里有哪些动作。现在可以先记录自己的想法。',
    suggestions:['这一步要整理什么？','哪些计算需要重复？'],topic:'算法步骤'},
  {id:'explore_2d' as ActivityId,number:3,title:'看看二维分组结果',goal:'上传表格，运行分组，再一起解释散点图。',
    introduction:'借阅次数和借阅时长，能不能一起比较？\n先来看看活动3："部分图书馆书籍数据.xlsx"这个表格。',
    pending:'',
    guidance:'上传Excel，确认要比较的两列，运行分组。看一看横轴、纵轴分别是什么，再比较两种颜色的点集中在哪里。',
    suggestions:['之后可以上传什么表？','我想知道图里的点是什么意思'],topic:'二维结果'},
]

export const previewBooks=[{name:'种梨',count:2},{name:'傲慢与偏见',count:6},{name:'如果历史是一群猫',count:9},{name:'浙江寻宝记',count:16},{name:'奇妙博物院',count:18}]
// This is an intentionally unordered display of future cards, not a submitted answer.
export const previewSteps=[{id:'repeat',text:'重复计算，直到分组稳定'},{id:'data',text:'获取并整理数据'},{id:'centers',text:'选择开始的中心'},{id:'count',text:'确定分成几组'}]
