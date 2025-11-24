-- ====================================================================
-- 主从表数据同步脚本
-- 生成时间: 2025-11-19 18:17:02
-- --------------------------------------------------------------------
-- 同步规则:
--   源主表: t_kl_service_instance
--   源从表: t_kl_service_instance_property
--   目标主表: t_kl_service_instance_dest
--   目标从表: t_kl_service_instance_property_dest
--   主表唯一标识: service_name
--   主从关联字段: service_id
--   从表唯一标识: param
--   过滤条件: is_del = 0 AND service_name like '%南向%'
-- ====================================================================

CREATE PROCEDURE Sync_t_kl_service_instance_20251119181702()
BEGIN
    -- 1. 声明变量
    DECLARE done INT DEFAULT 0;
    DECLARE src_main_id int; -- 源主表主键
    DECLARE src_unique_key varchar(255); -- 源主表唯一标识键
    DECLARE dest_main_id int; -- 目标主表主键
    
    -- 2. 定义游标

    DECLARE main_cursor CURSOR FOR
        SELECT `id`, `service_name` 
        FROM t_kl_service_instance
        WHERE is_del = 0 AND service_name like '%南向%';
    DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = 1;

    
    -- 3. 定义事务异常处理
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        SELECT '同步失败，事务已回滚' AS result;
    END;

    -- 4. 开启事务
    START TRANSACTION;

    -- 5. 打开游标并开始循环
    OPEN main_cursor;
    main_loop: LOOP
        -- 从游标获取一行源主表数据
        FETCH main_cursor INTO src_main_id, src_unique_key;
        
        IF done = 1 THEN
            LEAVE main_loop;
        END IF;

        -- 核心同步逻辑


        -- 5.1. 同步主表
        SET dest_main_id = NULL;
        
        -- 使用独立的BEGIN-END块来隔离NOT FOUND处理，防止误触发外层循环的done标记
        BEGIN
            DECLARE CONTINUE HANDLER FOR NOT FOUND SET dest_main_id = NULL;
            SELECT `id` INTO dest_main_id
            FROM t_kl_service_instance_dest
            WHERE `service_name` = src_unique_key;
        END;

        IF dest_main_id IS NOT NULL THEN
            UPDATE t_kl_service_instance_dest dest
            INNER JOIN t_kl_service_instance src ON src.`id` = src_main_id
            SET 
            dest.`application` = src.`application`,
            dest.`auth_company` = src.`auth_company`,
            dest.`connect_timeout` = src.`connect_timeout`,
            dest.`contact_number` = src.`contact_number`,
            dest.`contact_person` = src.`contact_person`,
            dest.`create_user` = src.`create_user`,
            dest.`data_source` = src.`data_source`,
            dest.`data_source_id` = src.`data_source_id`,
            dest.`data_type` = src.`data_type`,
            dest.`dataset_chinese_name` = src.`dataset_chinese_name`,
            dest.`dataset_english_name` = src.`dataset_english_name`,
            dest.`describe` = src.`describe`,
            dest.`interface_type` = src.`interface_type`,
            dest.`interface_url` = src.`interface_url`,
            dest.`is_asynchronous_service` = src.`is_asynchronous_service`,
            dest.`is_del` = src.`is_del`,
            dest.`is_own_use` = src.`is_own_use`,
            dest.`original_service_name` = src.`original_service_name`,
            dest.`prior_state` = src.`prior_state`,
            dest.`protocol_type` = src.`protocol_type`,
            dest.`publish_time` = src.`publish_time`,
            dest.`read_timeout` = src.`read_timeout`,
            dest.`request_mode` = src.`request_mode`,
            dest.`resource_id` = src.`resource_id`,
            dest.`resource_version` = src.`resource_version`,
            dest.`responsible_person` = src.`responsible_person`,
            dest.`secure` = src.`secure`,
            dest.`service_category` = src.`service_category`,
            dest.`service_classify` = src.`service_classify`,
            dest.`service_grade` = src.`service_grade`,
            dest.`service_identifier` = src.`service_identifier`,
            dest.`service_instance_id` = src.`service_instance_id`,
            dest.`service_name` = src.`service_name`,
            dest.`service_operate_type` = src.`service_operate_type`,
            dest.`service_proxy_url` = src.`service_proxy_url`,
            dest.`service_source` = src.`service_source`,
            dest.`service_source_application` = src.`service_source_application`,
            dest.`service_source_project` = src.`service_source_project`,
            dest.`service_source_resource` = src.`service_source_resource`,
            dest.`service_supply_way` = src.`service_supply_way`,
            dest.`service_tag` = src.`service_tag`,
            dest.`service_type` = src.`service_type`,
            dest.`service_url` = src.`service_url`,
            dest.`state` = src.`state`,
            dest.`tenant_id` = src.`tenant_id`,
            dest.`update_time` = src.`update_time`,
            dest.`update_user` = src.`update_user`,
            dest.`version` = src.`version`,
            dest.`view_name` = src.`view_name`
            WHERE dest.`id` = dest_main_id;
        ELSE
            INSERT INTO t_kl_service_instance_dest (
            `application`,
            `auth_company`,
            `connect_timeout`,
            `contact_number`,
            `contact_person`,
            `create_user`,
            `data_source`,
            `data_source_id`,
            `data_type`,
            `dataset_chinese_name`,
            `dataset_english_name`,
            `describe`,
            `interface_type`,
            `interface_url`,
            `is_asynchronous_service`,
            `is_del`,
            `is_own_use`,
            `original_service_name`,
            `prior_state`,
            `protocol_type`,
            `publish_time`,
            `read_timeout`,
            `request_mode`,
            `resource_id`,
            `resource_version`,
            `responsible_person`,
            `secure`,
            `service_category`,
            `service_classify`,
            `service_grade`,
            `service_identifier`,
            `service_instance_id`,
            `service_name`,
            `service_operate_type`,
            `service_proxy_url`,
            `service_source`,
            `service_source_application`,
            `service_source_project`,
            `service_source_resource`,
            `service_supply_way`,
            `service_tag`,
            `service_type`,
            `service_url`,
            `state`,
            `tenant_id`,
            `update_time`,
            `update_user`,
            `version`,
            `view_name`
            )
            SELECT 
            src.`application`,
            src.`auth_company`,
            src.`connect_timeout`,
            src.`contact_number`,
            src.`contact_person`,
            src.`create_user`,
            src.`data_source`,
            src.`data_source_id`,
            src.`data_type`,
            src.`dataset_chinese_name`,
            src.`dataset_english_name`,
            src.`describe`,
            src.`interface_type`,
            src.`interface_url`,
            src.`is_asynchronous_service`,
            src.`is_del`,
            src.`is_own_use`,
            src.`original_service_name`,
            src.`prior_state`,
            src.`protocol_type`,
            src.`publish_time`,
            src.`read_timeout`,
            src.`request_mode`,
            src.`resource_id`,
            src.`resource_version`,
            src.`responsible_person`,
            src.`secure`,
            src.`service_category`,
            src.`service_classify`,
            src.`service_grade`,
            src.`service_identifier`,
            src.`service_instance_id`,
            src.`service_name`,
            src.`service_operate_type`,
            src.`service_proxy_url`,
            src.`service_source`,
            src.`service_source_application`,
            src.`service_source_project`,
            src.`service_source_resource`,
            src.`service_supply_way`,
            src.`service_tag`,
            src.`service_type`,
            src.`service_url`,
            src.`state`,
            src.`tenant_id`,
            src.`update_time`,
            src.`update_user`,
            src.`version`,
            src.`view_name`
            FROM t_kl_service_instance src
            WHERE src.`id` = src_main_id;
            
            SET dest_main_id = LAST_INSERT_ID();
        END IF;


        -- 5.2. 同步从表
        --   a. 删除目标从表中不再存在的记录
        DELETE FROM t_kl_service_instance_property_dest
        WHERE `service_id` = dest_main_id
          AND `param` NOT IN (
            SELECT `param`
            FROM t_kl_service_instance_property
            WHERE `service_id` = src_main_id
          );

        --   b. 更新目标从表中已存在的记录
        UPDATE t_kl_service_instance_property_dest dest
        INNER JOIN t_kl_service_instance_property src 
            ON dest.`service_id` = dest_main_id 
           AND dest.`param` = src.`param`
        SET
            dest.`application` = src.`application`,
            dest.`create_user` = src.`create_user`,
            dest.`domain_id` = src.`domain_id`,
            dest.`element_id` = src.`element_id`,
            dest.`is_del` = src.`is_del`,
            dest.`param` = src.`param`,
            dest.`update_time` = src.`update_time`,
            dest.`update_user` = src.`update_user`,
            dest.`value` = src.`value`
        WHERE src.`service_id` = src_main_id;

        --   c. 插入源从表中新增的记录
        INSERT INTO t_kl_service_instance_property_dest (
            `service_id`,
            `application`,
            `create_user`,
            `domain_id`,
            `element_id`,
            `is_del`,
            `param`,
            `update_time`,
            `update_user`,
            `value`
        )
        SELECT
            dest_main_id,
            src.`application`,
            src.`create_user`,
            src.`domain_id`,
            src.`element_id`,
            src.`is_del`,
            src.`param`,
            src.`update_time`,
            src.`update_user`,
            src.`value`
        FROM t_kl_service_instance_property src
        LEFT JOIN t_kl_service_instance_property_dest dest
            ON dest.`service_id` = dest_main_id
           AND dest.`param` = src.`param`
        WHERE src.`service_id` = src_main_id
          AND dest.`id` IS NULL;



    END LOOP main_loop;
    CLOSE main_cursor;

    -- 6. 提交事务
    COMMIT;
    SELECT '同步成功' AS result;

END;