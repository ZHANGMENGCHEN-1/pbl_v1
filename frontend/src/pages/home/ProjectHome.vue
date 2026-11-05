<script setup lang="ts">
import { ArrowRight, Position } from '@element-plus/icons-vue'

const projects = [
  { id: 'astronomy-lab', number: '01', title: '天文观测', theme: 'astronomy', tag: '天文与科学', description: '构建观测助手，结合天气与星历，探索月球和行星的观测条件。', topics: ['System Prompt', '工具调用', '观测规划'] },
  { id: 'library-recommendation', number: '02', title: '图书馆采购推荐', theme: 'library', tag: '数据与决策', description: '从图书分组到阅读兴趣分析，用 K-Means 和智能体制定采购建议。', topics: ['聚类分析', '工具配置', '证据与反思'] },
]
</script>

<template>
  <div class="project-home">
    <header class="home-header">
      <div class="home-header-inner">
        <RouterLink to="/" class="home-brand" aria-label="Orbit 项目首页"><span class="brand-mark"><el-icon><Position/></el-icon></span><span>orbit</span><span class="home-brand-label">PBL 学习空间</span></RouterLink>
        <nav class="home-nav" aria-label="顶部菜单"><RouterLink to="/" class="home-current" aria-current="page">项目首页</RouterLink><RouterLink to="/projects/astronomy-lab">天文观测</RouterLink><RouterLink to="/projects/library-recommendation">图书馆采购推荐</RouterLink></nav>
      </div>
    </header>
    <main class="home-content">
      <section class="home-intro"><span class="home-eyebrow">从问题出发，在实践中学习</span><h1>选择你的学习项目</h1><p>定义问题，构建智能体，用证据发现答案。</p></section>
      <section class="home-project-grid" aria-label="学习项目">
        <RouterLink v-for="project in projects" :key="project.id" :to="'/projects/'+project.id" class="home-project-card" :class="project.theme">
          <div class="home-card-art" aria-hidden="true">
            <span class="home-project-number">PROJECT {{ Number(project.number) }}</span><span class="home-category">{{project.tag}}</span>
            <svg v-if="project.theme==='astronomy'" viewBox="0 0 560 235" class="home-project-illustration">
              <defs><radialGradient id="home-moon-light" cx="32%" cy="24%"><stop offset="0" stop-color="#fff"/><stop offset=".68" stop-color="#e9e1fa"/><stop offset="1" stop-color="#b9a8de"/></radialGradient></defs>
              <ellipse cx="282" cy="143" rx="186" ry="51" fill="none" stroke="#d9cdef" stroke-width="1.2" transform="rotate(-17 282 143)"/>
              <ellipse cx="282" cy="143" rx="144" ry="83" fill="none" stroke="#e3daf3" stroke-dasharray="4 7" transform="rotate(-17 282 143)"/>
              <circle cx="282" cy="130" r="61" fill="url(#home-moon-light)"/><circle cx="260" cy="111" r="11" fill="#d3c6e9" opacity=".5"/><circle cx="301" cy="147" r="17" fill="#c9bade" opacity=".45"/><circle cx="266" cy="156" r="7" fill="#bca8d5" opacity=".35"/>
              <circle cx="434" cy="92" r="17" fill="#9d8bc4"/><path d="M415 94 Q434 103 454 87" fill="none" stroke="#c4b4df" stroke-width="6"/>
              <circle cx="117" cy="177" r="9" fill="#b3a0d4"/>
              <g fill="#bba7d8"><circle cx="143" cy="58" r="2"/><circle cx="370" cy="45" r="2"/><circle cx="400" cy="192" r="2"/><circle cx="200" cy="200" r="2"/><path d="M180 85h12m-6-6v12" stroke="#af94d0"/><path d="M470 162h10m-5-5v10" stroke="#af94d0"/></g>
            </svg>
            <svg v-else viewBox="0 0 560 235" class="home-project-illustration">
              <rect x="254" y="58" width="188" height="122" rx="12" fill="#fff" stroke="#d9e6e3"/>
              <path d="M276 157V83m0 74h142" fill="none" stroke="#c6d8d3" stroke-width="1.5"/>
              <g fill="#62a79b"><circle cx="296" cy="133" r="5"/><circle cx="310" cy="143" r="5"/><circle cx="318" cy="124" r="5"/><circle cx="298" cy="115" r="5"/></g><g fill="#a68bc9"><circle cx="365" cy="102" r="5"/><circle cx="380" cy="86" r="5"/><circle cx="388" cy="110" r="5"/><circle cx="401" cy="96" r="5"/></g>
              <path d="M302 130l11 11m0-11-11 11m72-41 11 11m0-11-11 11" fill="none" stroke="#597c75" stroke-width="2"/>
              <rect x="133" y="169" width="130" height="22" rx="5" fill="#72a99f"/><path d="M145 180h105" stroke="#a5cbc3"/>
              <rect x="121" y="142" width="128" height="23" rx="5" fill="#b6a2d4"/><path d="M134 154h101" stroke="#d5c7e8"/>
              <rect x="141" y="112" width="113" height="26" rx="5" fill="#e1c393"/><path d="M153 125h89" stroke="#f4e4ca"/>
              <path d="M165 72q24-7 44 6v46q-21-13-44-6zm44 6q20-13 44-6v46q-24-7-44 6z" fill="#fffdf9" stroke="#c4b89f" stroke-width="1.5"/><path d="M209 79v44" stroke="#c4b89f"/>
              <circle cx="119" cy="73" r="3" fill="#a8c8be"/><circle cx="438" cy="198" r="3" fill="#b6a2d4"/>
            </svg>
          </div>
          <div class="home-card-content"><h2>{{project.title}}</h2><p>{{project.description}}</p><div class="home-topics"><span v-for="topic in project.topics" :key="topic">{{topic}}</span></div><div class="home-card-action"><span>进入项目</span><el-icon><ArrowRight/></el-icon></div></div>
        </RouterLink>
      </section>
    </main>
  </div>
</template>

<style scoped>
.project-home{min-height:100dvh;background:#f7f8fc;color:#30394e;font-size:16px}
.home-header{position:fixed;top:0;left:0;right:0;height:76px;z-index:50;background:rgba(255,255,255,.97);border-bottom:1px solid #e8eaf0}
.home-header-inner{max-width:1240px;height:100%;margin:auto;padding:0 32px;display:flex;align-items:center;justify-content:space-between;gap:24px}
.home-brand{display:flex;align-items:center;gap:10px;text-decoration:none;color:#292539;font-size:28px;font-weight:750;letter-spacing:-1px;white-space:nowrap}
.home-brand-label{border-left:1px solid #e2e4ec;padding-left:20px;margin-left:12px;font-size:16px;letter-spacing:0;font-weight:600;color:#596177}
.home-nav{display:flex;align-items:center;gap:30px;height:100%;white-space:nowrap}
.home-nav a{display:flex;align-items:center;height:100%;border-bottom:2px solid transparent;padding-top:2px;color:#687187;text-decoration:none;font-size:15px}
.home-nav a:hover,.home-nav .home-current{color:#7656b1}
.home-nav .home-current{border-bottom-color:#8060c1;font-weight:650}
.home-content{max-width:1176px;margin:0 auto;padding:144px 32px 80px}
.home-intro{margin-bottom:44px}
.home-eyebrow{font-size:14px;color:#80679f;letter-spacing:1px}
.home-intro h1{font-size:34px;font-weight:700;line-height:1.5;color:#30394e;margin:12px 0}
.home-intro p{font-size:16px;line-height:1.8;color:#657085}
.home-project-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:30px}
.home-project-card{display:block;overflow:hidden;border:1px solid #e3e5ef;border-radius:16px;background:#fff;color:inherit;text-decoration:none;box-shadow:0 5px 20px #39314b04;transition:transform .2s,box-shadow .2s,border-color .2s}
.home-project-card:hover{transform:translateY(-4px);box-shadow:0 12px 32px #53406b10;border-color:#c7b6e3}
.home-project-card:focus-visible{outline:3px solid #9f86ce;outline-offset:4px}
.home-card-art{position:relative;height:255px;background:#f2eef9;border-bottom:1px solid #ece6f3}
.library .home-card-art{background:#eef5f2;border-bottom-color:#e2ebe7}
.home-project-number{position:absolute;left:28px;top:22px;color:#80679f;font-size:13px;font-weight:700;letter-spacing:1.5px}
.library .home-project-number{color:#568c7e}
.home-category{position:absolute;right:26px;top:20px;border:1px solid #ddd3ed;border-radius:5px;padding:4px 9px;font-size:13px;color:#8c77a9;background:#ffffff70}
.library .home-category{color:#638d80;border-color:#d1e3da}
.home-project-illustration{width:100%;height:100%;padding-top:15px}
.home-card-content{padding:28px 28px 22px}
.home-card-content h2{font-size:23px;font-weight:700;color:#354056;line-height:1.5}
.home-card-content>p{font-size:16px;line-height:1.85;color:#657085;margin:12px 0 22px;min-height:60px}
.home-topics{display:flex;gap:9px;flex-wrap:wrap}
.home-topics span{font-size:13px;padding:5px 9px;border-radius:5px;background:#f6f5fa;color:#82738e}
.library .home-topics span{background:#f2f7f4;color:#688a7d}
.home-card-action{display:flex;align-items:center;justify-content:space-between;margin-top:26px;padding-top:20px;border-top:1px solid #eceef4;font-size:16px;font-weight:650;color:#7857ac}
.home-card-action>.el-icon{width:30px;height:30px;border-radius:50%;background:#f3eefb;font-size:17px;transition:transform .2s}
.home-project-card:hover .home-card-action>.el-icon{transform:translateX(3px)}
.library .home-card-action{color:#4e8978}
.library .home-card-action>.el-icon{background:#edf6f1}
@media(max-width:800px){.home-header-inner{padding:0 20px}.home-brand-label{display:none}.home-nav{gap:18px}.home-nav a{font-size:14px}.home-content{padding:118px 22px 50px}.home-intro h1{font-size:28px}.home-project-grid{gap:20px}.home-card-content{padding:22px}.home-card-art{height:215px}.home-project-number{left:20px}.home-category{right:16px}.home-card-content h2{font-size:20px}}
@media(max-width:580px){.home-header{height:68px}.home-brand{font-size:24px}.home-brand .brand-mark{width:27px;height:27px}.home-nav{gap:12px}.home-nav a{font-size:12px}.home-content{padding-top:105px}.home-project-grid{grid-template-columns:1fr}.home-intro{margin-bottom:28px}.home-card-art{height:230px}}
@media(prefers-reduced-motion:reduce){.home-project-card,.home-card-action>.el-icon{transition:none}.home-project-card:hover{transform:none}}
</style>
