# BiliRe - B站多账号自动回复系统

> 一个功能强大的B站多账号管理和自动回复工具，支持扫码登录、消息监控和智能回复

## ✨ 主要功能

### 🔐 账号管理
- **多账号支持**: 同时管理多个B站账号
- **扫码登录**: 安全便捷的二维码登录方式
- **Cookie管理**: 自动获取和维护登录状态
- **状态监控**: 实时监控账号登录状态和有效性

### 💬 消息系统
- **消息监控**: 实时监控私信和会话
- **消息显示**: 完整的消息历史记录查看
- **发送功能**: 支持向指定用户发送消息

### 🤖 自动回复
- **智能匹配**: 支持多种匹配模式（完全匹配、包含匹配、正则表达式）
- **规则管理**: 灵活的自动回复规则设置
- **延迟控制**: 可配置的回复延迟，避免被识别为机器人
- **每日限制**: 防止过度回复的每日消息限制
- **优先级系统**: 支持规则优先级排序

### 📊 统计分析
- **回复统计**: 详细的自动回复统计数据
- **会话分析**: 会话活跃度和消息频率分析
- **日志记录**: 完整的操作日志和调试信息

## 🚀 快速开始

### 环境要求
- Python 3.7+
- Windows/Linux/macOS

### 安装依赖
```bash
pip install -r requirements.txt
```

### 配置设置

1. **复制配置文件**:(可选步骤)
   ```bash
   cp config.example.json config.json
   cp bilibili_accounts.example.json bilibili_accounts.json
   ```

2. **修改配置文件**: 根据需要调整 `config.json` 中的设置（可选）

3. **运行程序**:
   ```bash
   python run_gui.py
   ```

## 📋 使用说明

### 1. 账号登录
1. 启动程序后，点击"登录新账号"
2. 扫描显示的二维码完成登录
3. 程序会自动保存登录信息

### 2. 设置自动回复
1. 在主界面选择账号
2. 点击"消息管理"进入消息管理界面
3. 添加自动回复规则：
   - **关键词**: 触发自动回复的关键词
   - **回复内容**: 自动回复的消息内容
   - **匹配类型**: 选择匹配模式
   - **优先级**: 设置规则优先级

### 3. 启动自动回复
1. 在消息管理界面启用"自动回复"
2. 设置回复延迟和每日限制
3. 程序将自动监控并回复消息

## ⚙️ 配置说明

### config.json 配置项(可选，程序会自动生成)

```json
{
  "window": {
    "width": 800,           // 窗口宽度
    "height": 600,          // 窗口高度
    "center_on_screen": true // 是否居中显示
  },
  "qrcode": {
    "size": [250, 250],     // 二维码尺寸
    "refresh_interval": 2000, // 刷新间隔(毫秒)
    "timeout": 180          // 超时时间(秒)
  },
  "network": {
    "timeout": 10,          // 网络超时时间
    "retry_count": 3        // 重试次数
  }
}
```

### 自动回复规则配置

- **完全匹配**: 消息内容与关键词完全相同才触发
- **包含匹配**: 消息内容包含关键词就触发
- **正则表达式**: 使用正则表达式进行模式匹配

## 🔧 高级功能

### 调试模式
程序提供详细的调试信息：
- 会话列表检查
- 消息内容分析
- API调用状态
- 匹配规则调试

### 批量操作
- 批量添加/删除自动回复规则
- 批量导入/导出配置
- 批量账号管理

## 🛡️ 安全说明

- **Cookie安全**: 程序使用本地存储，不会上传个人信息
- **账号保护**: 支持延迟和限制机制，降低被封风险
- **数据加密**: 敏感信息采用加密存储

## 📝 注意事项

1. **遵守B站规则**: 请合理使用自动回复功能，避免违反B站用户协议
2. **频率控制**: 建议设置适当的回复延迟，避免被识别为机器人
3. **内容规范**: 确保自动回复内容符合平台规范
4. **账号安全**: 定期检查账号状态，及时更新登录信息
5. **风控限制**: ⚠️ **重要提醒** - 如果对方没有关注你，在对方多次回复后可能会被B站风控系统限制，导致无法收到对方的消息或文件。建议引导用户关注后再进行深度交流

## 🤝 贡献指南

欢迎提交Issue和Pull Request来改进项目！

### 开发环境设置
```bash
# 克隆项目
git clone https://github.com/your-username/BiliRe.git
cd BiliRe

# 安装依赖
pip install -r requirements.txt

# 运行程序
python run_gui.py
```

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## 🙏 致谢

感谢所有为这个项目做出贡献的开发者！

## ⚠️ 免责声明

本工具仅供学习和研究使用，使用者需要遵守相关法律法规和平台规则。作者不对使用本工具造成的任何后果承担责任。

---

如果这个项目对你有帮助，请给个 ⭐️ Star 支持一下！ 
