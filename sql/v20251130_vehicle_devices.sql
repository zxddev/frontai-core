-- 车辆-设备关联表
-- 表示具体设备归属于具体车辆的绑定关系

-- 1. 创建关联表
CREATE TABLE IF NOT EXISTS operational_v2.vehicle_devices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vehicle_id UUID NOT NULL REFERENCES operational_v2.vehicles_v2(id) ON DELETE CASCADE,
    device_id UUID NOT NULL REFERENCES operational_v2.devices_v2(id) ON DELETE CASCADE,
    is_default BOOLEAN DEFAULT TRUE,  -- 是否为默认配置（出车时默认携带）
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT uq_vehicle_device UNIQUE (vehicle_id, device_id)
);

-- 2. 创建索引
CREATE INDEX IF NOT EXISTS idx_vehicle_devices_vehicle ON operational_v2.vehicle_devices(vehicle_id);
CREATE INDEX IF NOT EXISTS idx_vehicle_devices_device ON operational_v2.vehicle_devices(device_id);

-- 3. 添加注释
COMMENT ON TABLE operational_v2.vehicle_devices IS '车辆-设备关联表，定义每辆车的专属设备配置';
COMMENT ON COLUMN operational_v2.vehicle_devices.vehicle_id IS '车辆ID';
COMMENT ON COLUMN operational_v2.vehicle_devices.device_id IS '设备ID';
COMMENT ON COLUMN operational_v2.vehicle_devices.is_default IS '是否为默认配置，出车时默认携带';

-- 4. 插入示例数据：按车辆类型分配设备

-- 多功能无人机输送车 (f44f9f10-11ee-4b34-ad61-5faefabeaf10) -> 无人机
INSERT INTO operational_v2.vehicle_devices (vehicle_id, device_id) VALUES
('f44f9f10-11ee-4b34-ad61-5faefabeaf10', 'a9980fbf-75c8-4996-b0c1-01534859dc18'),  -- 扫图建模无人机
('f44f9f10-11ee-4b34-ad61-5faefabeaf10', '5fd2db2b-b280-4792-ad2c-13a16e233dd7'),  -- 灾情侦察无人机
('f44f9f10-11ee-4b34-ad61-5faefabeaf10', 'e6165dac-d574-4c91-8a25-b377634e86ce'),  -- 侦察无人机
('f44f9f10-11ee-4b34-ad61-5faefabeaf10', 'e4787711-741d-46b1-a671-15a284ba7492'),  -- 热成像无人机
('f44f9f10-11ee-4b34-ad61-5faefabeaf10', '50be37cd-157e-4e71-a4d9-b27891f5c61a'),  -- 物资投送无人机
('f44f9f10-11ee-4b34-ad61-5faefabeaf10', 'aa7b1d0b-dae9-4437-bca5-e7c437ea0b26')   -- 医疗救援无人机
ON CONFLICT (vehicle_id, device_id) DO NOTHING;

-- 多功能无人艇输送车 (9f1043d3-46c5-42a9-9c61-dde92471673a) -> 无人艇
INSERT INTO operational_v2.vehicle_devices (vehicle_id, device_id) VALUES
('9f1043d3-46c5-42a9-9c61-dde92471673a', '5303ec04-a3d7-41f4-8d61-c5aaf88b0925'),  -- 冲锋舟
('9f1043d3-46c5-42a9-9c61-dde92471673a', '00c27d1e-b095-4bbe-bde4-44afd15e582d'),  -- 人员搜救无人艇
('9f1043d3-46c5-42a9-9c61-dde92471673a', '5647dcd7-c6dc-4d01-bd11-a7fec3dd43d7'),  -- 无人救援艇
('9f1043d3-46c5-42a9-9c61-dde92471673a', '5f13e299-4063-4034-ac4d-746b5a703263'),  -- 物资运输无人艇
('9f1043d3-46c5-42a9-9c61-dde92471673a', '409b9363-a34a-4041-97e1-8fa24afd17a2')   -- 灾情侦察无人艇
ON CONFLICT (vehicle_id, device_id) DO NOTHING;

-- 前突侦察控制车 (692848b7-9f5b-4d3e-bc43-f662bc97b9e7) -> 机器狗
INSERT INTO operational_v2.vehicle_devices (vehicle_id, device_id) VALUES
('692848b7-9f5b-4d3e-bc43-f662bc97b9e7', '97e00c6f-4ce7-4ae2-9116-c0ba6c9c0b8e'),  -- 人员搜救机器狗
('692848b7-9f5b-4d3e-bc43-f662bc97b9e7', 'f3097b10-df19-4f00-ba73-f88109cdeca4'),  -- 搜救犬
('692848b7-9f5b-4d3e-bc43-f662bc97b9e7', 'edaa9c42-3929-4ee1-a01d-e8e9dafda59f'),  -- 通讯组网机器狗
('692848b7-9f5b-4d3e-bc43-f662bc97b9e7', 'aa5dc6fb-3ee4-4a5f-a4ee-6f1ce2d69fa3'),  -- 灾情分析机器狗
('692848b7-9f5b-4d3e-bc43-f662bc97b9e7', '2625c678-892b-4e4c-9005-fe9039cb8d4f')   -- 灾情侦察机器狗
ON CONFLICT (vehicle_id, device_id) DO NOTHING;

-- 医疗救援车 (1bfd0948-e79f-4927-8b04-f3db53b5c393) -> 医疗设备
INSERT INTO operational_v2.vehicle_devices (vehicle_id, device_id) VALUES
('1bfd0948-e79f-4927-8b04-f3db53b5c393', '36a2e5ec-2b70-4dfd-8fef-1e51558dd982'),  -- 便携呼吸机
('1bfd0948-e79f-4927-8b04-f3db53b5c393', '9fd5319f-c5a2-4ecc-a118-0ceda6a44962'),  -- 高级急救包
('1bfd0948-e79f-4927-8b04-f3db53b5c393', 'ea33b289-b3d6-446e-8b01-c8cf8d36b4c7'),  -- 急救医疗包
('1bfd0948-e79f-4927-8b04-f3db53b5c393', 'ef0dc82b-1f47-4411-9b87-383e894d37bb'),  -- 静脉输液套装
('1bfd0948-e79f-4927-8b04-f3db53b5c393', '3d79ed58-339a-4f5e-baf9-b89ec3649895'),  -- 生命体征监护仪
('1bfd0948-e79f-4927-8b04-f3db53b5c393', 'a69adaa0-a907-46f9-8bc3-9b937673236a'),  -- AED除颤仪
('1bfd0948-e79f-4927-8b04-f3db53b5c393', 'bb382b42-d08e-4fcd-b78c-f537097c8015')   -- 医疗帐篷
ON CONFLICT (vehicle_id, device_id) DO NOTHING;

-- 综合保障车 (e87feefc-6d4f-4d24-b2c2-1d15c9a6e505) -> 工程/通讯设备
INSERT INTO operational_v2.vehicle_devices (vehicle_id, device_id) VALUES
('e87feefc-6d4f-4d24-b2c2-1d15c9a6e505', 'da090efa-c8ee-47ef-9db5-78e52296fc09'),  -- 发电机
('e87feefc-6d4f-4d24-b2c2-1d15c9a6e505', '1d268c90-af25-43de-977b-c1de71fb0e39'),  -- 移动照明灯塔
('e87feefc-6d4f-4d24-b2c2-1d15c9a6e505', 'b2f51050-fd43-4e18-8b74-07fcad602db6'),  -- 卫星电话
('e87feefc-6d4f-4d24-b2c2-1d15c9a6e505', '709a3505-fe32-495d-b827-fce0a5cb7a4a'),  -- 中继台
('e87feefc-6d4f-4d24-b2c2-1d15c9a6e505', '790b4ffd-4d38-43f3-9a13-26410d928be5'),  -- 对讲机
('e87feefc-6d4f-4d24-b2c2-1d15c9a6e505', 'd6560629-8b41-487a-bbab-1213fb90638b')   -- 扩音器
ON CONFLICT (vehicle_id, device_id) DO NOTHING;

-- 全地形越野指挥车 (15fe43c7-4b3f-4ac6-b764-d0fcdd5608eb) -> 探测/救援设备
INSERT INTO operational_v2.vehicle_devices (vehicle_id, device_id) VALUES
('15fe43c7-4b3f-4ac6-b764-d0fcdd5608eb', '5089c487-6ba5-444b-9a8c-969076eb49c6'),  -- 雷达生命探测仪
('15fe43c7-4b3f-4ac6-b764-d0fcdd5608eb', 'f4f9937d-8673-487c-b8e8-08cc188b49b5'),  -- 蛇眼探测仪
('15fe43c7-4b3f-4ac6-b764-d0fcdd5608eb', '6a77a75d-4faf-49c8-9521-de6e5bb58e56'),  -- 音频生命探测仪
('15fe43c7-4b3f-4ac6-b764-d0fcdd5608eb', '1326edd8-ec6a-4453-aa6e-2477a6d362a5'),  -- 气体检测仪
('15fe43c7-4b3f-4ac6-b764-d0fcdd5608eb', '9ba1aca7-ab3a-4687-9c5b-ea17d419f156'),  -- 强光手电
('15fe43c7-4b3f-4ac6-b764-d0fcdd5608eb', '387e28c3-e61e-437c-98f6-52d287bba363'),  -- 液压剪切器
('15fe43c7-4b3f-4ac6-b764-d0fcdd5608eb', 'ef73edf1-037f-4685-ae6a-019e3c97d0b7'),  -- 液压扩张器
('15fe43c7-4b3f-4ac6-b764-d0fcdd5608eb', '36c12b18-5204-4b9d-bc6b-f63b5a001678')   -- 救援千斤顶
ON CONFLICT (vehicle_id, device_id) DO NOTHING;
