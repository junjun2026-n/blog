const databaseForm=document.querySelector('form.panel');
databaseForm.addEventListener('submit',event=>{
  if(event.submitter?.value==='initialize'&&!confirm('初始化表单中的目标数据库？已有数据保留，不切换当前连接，不迁移文章和评论。'))event.preventDefault();
});
document.getElementById('db-eye').addEventListener('click',()=>{
  const password=document.getElementById('db-password');password.type=password.type==='password'?'text':'password';
  document.getElementById('db-eye').setAttribute('aria-label',password.type==='password'?'显示密码':'隐藏密码');
});
