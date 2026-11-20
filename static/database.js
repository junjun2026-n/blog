// ============================================================
// 文件名称：database.js
// 生成日期：2026-11-16
// 修改日期：2026-11-20
// 版本信息：v0.261115
// 作    者：JUN
// 备    注：本程序由AI辅助完成。
//           文件功能：管理数据库连接及数据访问。
//           文件用途：供博客的 BLOG/static/database.js 模块使用。
//           注意事项：运行前检查依赖与配置；涉及数据或服务变更时先备份并验证。
// ============================================================
const databaseForm=document.querySelector('form.panel');
databaseForm.addEventListener('submit',event=>{
  if(event.submitter?.value==='initialize'&&!confirm('初始化表单中的目标数据库？已有数据保留，不切换当前连接，不迁移文章和评论。'))event.preventDefault();
});
document.getElementById('db-eye').addEventListener('click',()=>{
  const password=document.getElementById('db-password');password.type=password.type==='password'?'text':'password';
  document.getElementById('db-eye').setAttribute('aria-label',password.type==='password'?'显示密码':'隐藏密码');
});
