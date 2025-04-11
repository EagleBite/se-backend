import os
import click
from flask import current_app
from sqlalchemy import inspect
import inspect as py_inspect
from collections import defaultdict
from .extensions import db

def register_commands(app):
    @app.cli.command("init-db")
    def init_db():
        """初始化数据库."""
        with app.app_context():
            logger = app.logger

            # 记录开始初始化
            logger.info("🚀 Starting database initialization")

            # 记录数据库配置
            db_uri = app.config['SQLALCHEMY_DATABASE_URI']
            logger.info(f"🔧 Database URI: {db_uri}")

            # 确保模型已导入
            try:
                from . import models
                logger.debug("All models imported successfully")
            except ImportError as e:
                logger.error(f"Model import failed: {str(e)}")
                raise

            # 创建表
            try:
                db.create_all()
                logger.info("✅ Database tables created")
                
                # 验证表是否创建成功
                from sqlalchemy import inspect
                inspector = inspect(db.engine)
                tables = inspector.get_table_names()
                logger.info(f"📊 Created tables: {tables}")

            except Exception as e:
                logger.error(f"❌ Database creation failed: {str(e)}", exc_info=True)
                raise

            logger.info("🎉 Database initialization completed successfully")

    @app.cli.command("drop-tables")
    @click.option('--force', is_flag=True, help='跳过确认直接执行')
    def drop_tables(force):
        """删除所有数据库表（危险操作！）"""
        with app.app_context():
            logger = app.logger

            # 生产环境保护
            if app.config.get("ENV") == 'production' and not force:
                logger.error("❌ 生产环境禁止直接删除表！")
                return

            # 安全确认
            if not force:
                tables = inspect(db.engine).get_table_names()
                click.echo("\n⚠️ 将要删除以下表：")
                for table in tables:
                    click.echo(f"  - {table}")

                if not click.confirm("\n❗ 确认要删除所有表吗？此操作不可恢复！"):
                    logger.info("取消删除操作")
                    return
                
            # 确保模型已导入
            try:
                from . import models
                logger.debug("All models imported successfully")
            except ImportError as e:
                logger.error(f"Model import failed: {str(e)}")
                raise
                
            try:
                logger.warning("🗑️ 开始删除数据库表...")
                db.drop_all()
            
                # 验证是否删除成功
                remaining_tables = inspect(db.engine).get_table_names()
                if not remaining_tables:
                    logger.info("✅ 所有表已成功删除")
                else:
                    logger.error(f"❌ 表删除不完整，剩余表: {remaining_tables}")

            except Exception as e:
                logger.error(f"删除表失败: {str(e)}", exc_info=True)
                raise


    @app.cli.command("list-routes")
    def list_routes():
        """列出所有API端点及其注释和HTTP方法."""
        from flask import current_app
        import inspect
        from collections import defaultdict

        routes = defaultdict(list)
       
        for rule in current_app.url_map.iter_rules():
            if not rule.endpoint.startswith('static'):  # 忽略静态文件路由
                # 获取视图函数
                view_func = current_app.view_functions[rule.endpoint]

                # 取函数文档字符串
                docstring = inspect.getdoc(view_func) or "无文档注释"
                docstring = ' '.join(line.strip() for line in docstring.split('\n'))

                # 获取支持的HTTP方法
                methods = sorted([m for m in rule.methods if m not in ('HEAD', 'OPTIONS')])

                routes[rule.endpoint].append({
                        "path": str(rule),
                        "methods": methods,
                        "doc": docstring
                    })
            
        # 格式化输出
        output = []
        for endpoint, infos in routes.items():
            for info in infos:
                output.append(
                    f"{', '.join(info['methods']):>10} {info['path']:50} {info['doc']}"
                )

        print("\nRegistered Routes:")
        print("-" * 120)
        print("\n".join(sorted(output)))
        print("-" * 120)
        print(f"Total: {len(output)} routes\n")