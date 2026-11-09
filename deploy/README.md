# 服务器部署与日常发布

当前目标：让合作者通过公网测试功能。保持单台服务器、SQLite和现有会话机制，不在本轮增加并发系统或登录功能。

固定工作方式：**本地开发测试 → 推送GitHub → 服务器发布**。服务器不直接修改业务代码；`.env`、数据库和备份不上传GitHub。

## 当前服务器约定

| 项目 | 当前值 |
| --- | --- |
| SSH别名 | `pbl-server`，在本机终端使用 |
| 登录用户 | `ecs-user` |
| 项目路径 | `/home/ecs-user/apps/pbl_v1` |
| 前端入口 | `/var/www/pbl` |
| 后端服务 | `pbl-backend`，监听 `127.0.0.1:8000` |
| 公网入口 | `http://8.136.241.217` |
| 服务器配置 | 项目下的 `backend/.env` |
| 默认数据库 | 项目下的 `backend/data/workspace.db` |
| 发布备份 | `/home/ecs-user/pbl-backups/` |
| 静态网页版本 | `/var/www/pbl-releases/` |

`DATABASE_PATH`如果是相对路径，按 `backend` 目录解析。发布脚本不修改`.env`、不替换工作数据库；备份脚本读取实际配置并使用SQLite在线备份接口，包含已经提交到WAL的数据。

## 一、本地完成修改

在**本机项目根目录**执行：

```powershell
git status
```

确认改动范围，不包含`.env`、数据库或私钥；运行与本次修改相关的测试。前端变更通常执行：

```powershell
cd frontend
npm.cmd run build
cd ..
```

后端变更通常执行：

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest tests -q
cd ..
```

然后提交、推送：

```powershell
git add .
git diff --cached --stat
git commit -m "描述本次修改"
git push origin main
```

这次新增的`deploy/`文件和`frontend/src/shared/api.ts`中的HTTP兼容修复应一起提交。未推送的本地代码不会到服务器上。

以后修改Python依赖时，应同时更新并验证`backend/requirements-lock.txt`；发布会优先使用锁定版本。Node依赖改动需一并提交`package-lock.json`。

## 二、仅第一次：取得发布脚本并处理服务器手动改动

从**本机终端**连接：

```text
ssh pbl-server
```

以下都在**Ubuntu服务器终端**执行：

```bash
cd ~/apps/pbl_v1
git status
git diff -- frontend/src/shared/api.ts
```

如果只有之前手动修改的`api.ts`，确认确实是`crypto.randomUUID()`兼容修复后，先将该文件修改存入Git stash，再拉取：

```bash
git stash push -m "server HTTP compatibility fix before unified deployment" -- frontend/src/shared/api.ts
git pull --ff-only origin main
```

服务器修改保存在stash中，没有丢弃。**不要执行`git stash pop`**：远端版本已经包含同样功能，重复应用可能冲突。若还有其他修改，先逐项检查；不要使用`git reset --hard`或`git clean`来消除提示。

如果工作区原本就是干净的，直接：

```bash
git pull --ff-only origin main
```

注意：这次初始拉取发生在脚本接管之前。原来正在运行的网页仍在`/var/www/pbl`中；之后用脚本建立第一份发布备份。

## 三、日常发布：一条命令

先确认没有合作者正在运行智能体；重启后端会中断运行中的请求。

```bash
cd ~/apps/pbl_v1
bash deploy/release.sh
```

脚本依次执行：

1. 检查工作区干净、处于`main`、服务路径匹配，并防止重复发布。
2. 获取`origin/main`，发现历史分歧就停止，不自动合并。
3. 记录旧提交编号，备份当前数据库、`.env`和正在提供的前端网页。
4. 快进更新代码，执行`npm ci`与`npm run build`。
5. 按`backend/requirements-lock.txt`安装依赖；没有锁文件时使用`requirements.txt`。
6. 新网页写入独立版本目录，不覆盖正在提供的文件。
7. 重启后端，检查`/api/health`；通过后切换网页版本，并检查Nginx入口。

看到`Release completed`才算脚本完成。然后在浏览器确认两个项目能进入、智能体能运行、提交记录正常。健康检查只验证基本可用性，不会调用付费模型，也不代表功能验收已经完成。

第一次接管时，原来的`/var/www/pbl`目录会保存到`pbl-releases/legacy-...`，随后网站入口改成指向版本目录的软链接，转换时可能短暂不可用。后续切换软链接不再逐个覆盖网页文件。已打开旧页面的浏览器可能需要刷新。

### 国内镜像设置（可选，只需一次）

如果服务器下载依赖慢，可在发布前设置：

```bash
cd ~/apps/pbl_v1
.venv/bin/python -m pip config set global.index-url https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple
npm config set registry https://registry.npmmirror.com
```

镜像可能同步滞后。如果锁定版本找不到，请保留报错，不要为了安装成功临时删除锁文件或随意升级依赖。

## 四、只改服务器.env

密钥属于服务器配置，不需要经过Git：

```bash
nano ~/apps/pbl_v1/backend/.env
sudo systemctl restart pbl-backend
sudo systemctl status pbl-backend --no-pager
```

不需要重新构建前端。供合作者持续测试时建议`LIBRARY_RESET_ON_REFRESH=false`，保留刷新后的学习记录。

## 五、发布失败和回退

构建失败时不会切换网页或主动重启后端，但Git工作区可能已更新，Python依赖也可能已部分变化。脚本不是完整的零停机发布系统，不会自动撤回代码、依赖、数据库变更。

每次发布会输出备份目录。例如：

```text
/home/ecs-user/pbl-backups/20261109T080000Z-1234-abcdef12
```

如果发布后有问题，使用**本次发布前的备份目录**回退：

```bash
cd ~/apps/pbl_v1
bash deploy/release.sh --rollback /home/ecs-user/pbl-backups/实际备份目录
```

这会先备份当前状态，再切换旧代码、安装旧版本依赖、恢复旧网页并重启后端。Git处于detached HEAD是正常现象：回退不重写`main`历史。下次准备发布已修复的新版本时：

```bash
git switch main
bash deploy/release.sh
```

**回退默认不恢复`.env`和数据库**，避免覆盖发布后新产生的学习记录。如果某次改动涉及不兼容的数据结构，需要先评估数据库恢复和新数据保留方案，再单独处理。不要在后端运行时直接覆盖`.db`文件，也不要将旧`.db`与当前的`-wal`混用。

备份和旧网页版本暂不自动删除；定期检查磁盘空间，确认有可用备份后再手动整理。备份中包含密钥和学习数据，目录仅供当前用户读取，不要上传GitHub或放进网站目录。

## 六、排查命令

```bash
sudo systemctl status pbl-backend --no-pager
sudo journalctl -u pbl-backend -n 80 --no-pager
curl -fsS http://127.0.0.1:8000/api/health
curl -fsS -H 'Host: 8.136.241.217' http://127.0.0.1/api/health
sudo nginx -t
git status
git log -3 --oneline
```

查看日志后可以发送错误信息排查，但先遮盖密钥和学生内容。

## 七、配置模板

`nginx.conf`和`pbl-backend.service`是当前服务器的参考模板。已有配置正常时，**无需为使用发布脚本重新安装模板**。脚本也不会自动覆盖Nginx或systemd配置。

以后新服务器首次部署、修改域名或调整路径时，再按实际情况修改模板、安装配置。Nginx变更先执行`sudo nginx -t`，通过后再reload；systemd变更后执行`sudo systemctl daemon-reload`再重启服务。
