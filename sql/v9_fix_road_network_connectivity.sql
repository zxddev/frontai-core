-- 路网连通性修复SQL
-- 自动生成：连接断开的路网分量

BEGIN;


INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '06586c67-7e98-4f95-8706-1898f225dc86'::uuid,
    '77ce23e1-4046-4044-ab5d-59a69be19f88'::uuid,
    '12b2df7e-2b62-4e32-8029-08ed0b7703a6'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(103.5607698, 31.4569156),
        ST_MakePoint(103.5604553, 31.4569627)
    ), 4326),
    'unclassified',
    30.29,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    'cb33ec71-0257-440d-8029-6ee3d7bd3838'::uuid,
    'c18bad80-6965-4dc7-af40-9eb5f0019d37'::uuid,
    'ad6f0064-75fb-4d8c-b321-0b04e06ae6cf'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(103.4892017, 31.5558183),
        ST_MakePoint(103.4891606, 31.5557356)
    ), 4326),
    'unclassified',
    9.99,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '8405715d-c993-4889-aac9-48eae9a84418'::uuid,
    '753e19e5-de4b-4f72-9aea-59d7bd91cf8a'::uuid,
    'd73671df-6c51-46a8-bd91-7e7242502db8'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.4028548, 31.2137204),
        ST_MakePoint(104.4053171, 31.2227092)
    ), 4326),
    'unclassified',
    1026.57,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '88ec3cbe-0487-496e-89ac-1822027cd2de'::uuid,
    '5ce25f65-c099-4919-af58-9b79c20862c5'::uuid,
    '11d044ec-2f35-4efc-ad35-87ff543ce51b'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.2955196, 31.3969943),
        ST_MakePoint(104.2957027, 31.3973942)
    ), 4326),
    'unclassified',
    47.74,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    'e838492e-4353-47e2-b349-4ed855c943a1'::uuid,
    'f73e50fe-94f4-4495-b25d-fb9823d31eaa'::uuid,
    'ecc878d0-b731-4c35-b268-bcbb34f0175b'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.0366927, 31.348152),
        ST_MakePoint(104.0363624, 31.3481923)
    ), 4326),
    'unclassified',
    31.68,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '895df9ef-ad2e-4294-86f3-1f087617075e'::uuid,
    '1858f880-cbe1-4f98-8d37-83349760889f'::uuid,
    '46afa2c7-557a-4101-9593-affd359be5b5'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.0568881, 31.2561013),
        ST_MakePoint(104.0589445, 31.2594598)
    ), 4326),
    'unclassified',
    421.51,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '2327d11c-e933-4e9c-ba65-7840979390b7'::uuid,
    '11d0841e-e7f4-423b-bb23-cc1584735fe8'::uuid,
    '85ce5bae-37c6-4a61-80e9-0d161c69b790'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.4247774, 31.3861723),
        ST_MakePoint(104.4247275, 31.386226)
    ), 4326),
    'unclassified',
    7.62,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '201b23ee-2dea-4d8a-8c04-d4a94db1716c'::uuid,
    '600f41a4-c411-4cf6-865a-767a55bf2cb2'::uuid,
    'd5647d6c-715f-447b-ba9c-2a00f67b7557'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.3151226, 31.8579311),
        ST_MakePoint(104.3166348, 31.8582055)
    ), 4326),
    'unclassified',
    146.04,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    'f51b0135-6126-4c38-80a5-f062b9145e90'::uuid,
    '0ef95a90-78c2-42e6-9aa5-d86da8c04f97'::uuid,
    '9ff78ce5-b535-4722-adf5-e53a37fa48b3'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.4658184, 31.2182242),
        ST_MakePoint(104.465752, 31.2181488)
    ), 4326),
    'unclassified',
    10.50,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '7d0f8b02-474a-4b86-be4d-2116db66cff0'::uuid,
    '8615f929-09e2-4f04-9bfd-95d45b18e973'::uuid,
    'cdef2e88-3026-4cb9-ac9e-f0f8e4953623'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.4520463, 31.8226232),
        ST_MakePoint(104.4528522, 31.8220618)
    ), 4326),
    'unclassified',
    98.46,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    'ad86a063-a673-45de-84f4-4b1f0782e6b7'::uuid,
    '1858f880-cbe1-4f98-8d37-83349760889f'::uuid,
    '756e57b3-a76f-48c0-8fa3-3f62a91531a9'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.0568881, 31.2561013),
        ST_MakePoint(104.0615419, 31.260841)
    ), 4326),
    'unclassified',
    688.07,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '9f0bd27e-5623-4096-9831-c80e6b502fa3'::uuid,
    '905d34e9-75f4-43ba-bfeb-d3abcf9eb573'::uuid,
    '6cf3e091-93f7-4dd6-8326-8d621665f741'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.339075, 31.2158777),
        ST_MakePoint(104.3389392, 31.2158294)
    ), 4326),
    'unclassified',
    13.99,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    'c07b7208-cd71-4a43-94cb-0b4ca451a734'::uuid,
    'aa7161c4-aa74-4996-8ec7-7d9b1975c06d'::uuid,
    'fd300c71-d2be-49e8-b7bb-8d3de5c33b76'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.4569037, 31.6190209),
        ST_MakePoint(104.4568543, 31.6188411)
    ), 4326),
    'unclassified',
    20.53,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    'f3162faf-31db-4684-8504-daf7cec5bb13'::uuid,
    '94ddf66a-a4b7-40cf-8ef6-ca4e6a9fca37'::uuid,
    'bd350a61-6171-4854-adc4-a72186d68795'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.4507568, 31.5026592),
        ST_MakePoint(104.4305074, 31.5056263)
    ), 4326),
    'unclassified',
    1947.89,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    'aa6ec8e5-21ed-495b-a3ac-d0c9462aa7a7'::uuid,
    '20fe8038-8aac-4835-a90c-307e729d6f21'::uuid,
    '6c92c381-7b88-4e5a-801d-0f732b0ca3a8'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.4646488, 31.6056853),
        ST_MakePoint(104.4660587, 31.6055997)
    ), 4326),
    'unclassified',
    133.86,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '40982aa2-d836-4b81-a0f6-38bdc179fa58'::uuid,
    '61579a5d-3e69-42b5-8a55-ea20f1b2da86'::uuid,
    '4e816ffa-1bf5-4ac9-99ba-f6fcf87af591'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.4295809, 31.2261281),
        ST_MakePoint(104.4269872, 31.225958)
    ), 4326),
    'unclassified',
    247.35,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    'df7a0652-cd3e-4e43-b74e-1f1b0c414797'::uuid,
    '5b1e7d03-320a-49de-8156-7bc2f41eb2cd'::uuid,
    '44424b71-b7bf-482e-b6bd-859bd2222f8e'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.4261689, 31.2182162),
        ST_MakePoint(104.4259285, 31.2182344)
    ), 4326),
    'unclassified',
    22.95,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '36ddaedb-6fd0-4d96-b850-90ef99e187fa'::uuid,
    '2087c8ee-59d2-412b-bcd4-cb01ae56898c'::uuid,
    '3d5c39c7-c771-4f20-9445-31596c82d2dc'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.3793869, 31.6033476),
        ST_MakePoint(104.381758, 31.5975084)
    ), 4326),
    'unclassified',
    687.03,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    'f52fd389-ba17-413d-b047-7ed30b362bed'::uuid,
    '41e6925b-3529-4796-be71-3c813260476d'::uuid,
    '08687fd3-0941-404d-b4ab-82e0cdd02eac'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.1954674, 31.2810276),
        ST_MakePoint(104.195548, 31.2834346)
    ), 4326),
    'unclassified',
    267.76,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    'd6cf2558-c7a8-49f9-9ee9-262cfd63529b'::uuid,
    'c95d8f7a-2aad-4f4a-8d63-6dab35db0731'::uuid,
    '59f2fa4f-e55b-4e7e-b989-029b61bf6db9'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(103.4666821, 31.2842582),
        ST_MakePoint(103.4678337, 31.2800909)
    ), 4326),
    'unclassified',
    476.13,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    'bd9a3a0e-688d-44b4-8341-ff5106dcd64d'::uuid,
    '75cfc8ff-7317-4137-9ead-ec7184ac6e44'::uuid,
    '3f5a6954-bfdb-4ddb-b20a-0392ccf18b64'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.4596594, 31.6138519),
        ST_MakePoint(104.4588219, 31.613575)
    ), 4326),
    'unclassified',
    85.07,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    'e1896249-a5cc-4dfd-8a51-2e40a5000d24'::uuid,
    '8aeba9c3-51b8-4c26-a209-c4672616ea96'::uuid,
    '05137046-04e0-42fd-a1ca-608d64e0cfc9'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.2776507, 31.3057549),
        ST_MakePoint(104.2773449, 31.3026496)
    ), 4326),
    'unclassified',
    346.51,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '01e22a4d-0d65-4287-b6d3-480a8861d02d'::uuid,
    'd3b13fca-06f3-408a-a86d-c5f34d9eb176'::uuid,
    '4b220279-6e48-4837-9978-5d185cedafa9'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.2274988, 31.2710821),
        ST_MakePoint(104.2206752, 31.2859136)
    ), 4326),
    'unclassified',
    1772.10,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '61d738f8-a527-413b-99cf-56080ae506d4'::uuid,
    '511a0a80-7af3-4b9e-8dd5-8b497a4fdfe7'::uuid,
    'b55bd1c4-08fc-4422-a235-7a4396a796cd'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.4238075, 31.2406328),
        ST_MakePoint(104.4316041, 31.2406794)
    ), 4326),
    'unclassified',
    741.25,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '9e0fce45-015c-419e-8826-ed0999f68c25'::uuid,
    '2d450746-932a-4205-9faf-653fa12962a4'::uuid,
    '10f06fe0-5b60-4e78-8f55-91bd22682529'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.3153689, 31.2688623),
        ST_MakePoint(104.3112965, 31.2685696)
    ), 4326),
    'unclassified',
    388.42,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '2c993915-fb7e-47fc-8199-8b956386e4a8'::uuid,
    'bdc58118-bc75-4897-a951-d837d7bd4ae7'::uuid,
    '64bf63ca-b430-49c0-a24e-cb5f2b1db75e'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(103.3334034, 31.5705159),
        ST_MakePoint(103.3357398, 31.5637622)
    ), 4326),
    'unclassified',
    782.92,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '858169d2-d734-4931-8dba-4761341d0a06'::uuid,
    'a3538a7c-ae8d-4858-be6a-bdaba3f26e9c'::uuid,
    '3fc48480-faf7-45f9-b5b4-44e6d974c164'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.4649923, 31.3043701),
        ST_MakePoint(104.4646652, 31.3052436)
    ), 4326),
    'unclassified',
    101.98,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '862f8489-a6cd-4bf8-b72a-6d245e5fbbf6'::uuid,
    '187d3579-36ce-43e2-8db0-6aec1e1d04a1'::uuid,
    'dea9dcb1-af73-4705-8dbc-61bc2c83375a'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(103.8530501, 31.7095448),
        ST_MakePoint(103.8538233, 31.7014121)
    ), 4326),
    'unclassified',
    907.27,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '75991e34-2c84-457f-ba37-1c50d6685f8f'::uuid,
    '41a27c6f-8f15-4409-8ddf-7ad56bc9365a'::uuid,
    'ba217737-3472-47f3-96c0-70567b5c7ab1'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(103.3831295, 31.5652698),
        ST_MakePoint(103.3885583, 31.5638746)
    ), 4326),
    'unclassified',
    537.23,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    'd210968b-7466-41fc-8e04-3af0d607c0ef'::uuid,
    '72ef38da-bfa5-4169-be53-9689266ecfdf'::uuid,
    '5fa153f6-d671-4662-80d2-7c6e45ebb6bd'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.4712384, 31.6169025),
        ST_MakePoint(104.4725707, 31.6175024)
    ), 4326),
    'unclassified',
    142.71,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '6bbf0475-c7c4-4fee-b5a8-5cb4a83d6e2b'::uuid,
    '5e11a765-823b-47bd-94e0-0a0e7e21f783'::uuid,
    '6e1fc531-9c7d-45e0-993d-4d0719df9a07'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.4749408, 31.5055646),
        ST_MakePoint(104.4757382, 31.5164738)
    ), 4326),
    'unclassified',
    1215.40,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '723fdfee-1d79-4b22-9537-4b91bc00b30d'::uuid,
    'ad8b01e7-b9aa-4227-bef5-943a66220628'::uuid,
    'b1924f54-c135-4414-b8aa-f684782d207c'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.3428301, 31.3006581),
        ST_MakePoint(104.3419692, 31.2951108)
    ), 4326),
    'unclassified',
    622.23,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    'f8c61cec-5cd7-4b02-b0e7-ffffd523e34c'::uuid,
    'ed41969f-8da6-46cc-b870-1f8fe05726e8'::uuid,
    '383bdf22-ac90-4684-8c48-088a7c3f1766'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(103.4336024, 31.5646231),
        ST_MakePoint(103.4521311, 31.5576616)
    ), 4326),
    'unclassified',
    1918.63,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '4a373c6e-6505-476a-86a6-c58fa712605d'::uuid,
    '06195e22-f9d2-41f2-8d4a-61e0f1c6c47e'::uuid,
    '1259c07c-8990-4c34-990e-ae521e7ea2a0'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.47328, 31.5987624),
        ST_MakePoint(104.4700712, 31.5966637)
    ), 4326),
    'unclassified',
    383.17,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '9ed5cd77-6c38-4234-82fc-cb959ad34675'::uuid,
    '0d3c22d5-bf23-4460-b95e-ad5c371d4bd6'::uuid,
    '333cc247-3e3c-4e3e-94f3-fe01b1cb2149'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.4693014, 31.5953377),
        ST_MakePoint(104.4691547, 31.595372)
    ), 4326),
    'unclassified',
    14.41,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    'fd81a1f0-0600-43e9-b408-1c5d5aeb2250'::uuid,
    'f37ee77e-60af-4385-b789-d88e98fa7b71'::uuid,
    '173635ce-7da1-40fd-8a3d-f1bf19058fa6'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.4345746, 31.6727594),
        ST_MakePoint(104.4320363, 31.671541)
    ), 4326),
    'unclassified',
    275.78,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    'a1c53034-396c-4d9f-a7fe-61e9f56d0dfb'::uuid,
    '7eefd11d-c3da-4f88-baf6-b57fd47637d8'::uuid,
    '935ef61a-84ce-4488-ac0d-b48e6162ca82'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.4663139, 31.6083817),
        ST_MakePoint(104.4665824, 31.6057837)
    ), 4326),
    'unclassified',
    290.00,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '59fafee7-6789-42f9-8eec-f7e57fb46ea8'::uuid,
    'b9939bc5-4e75-4955-9e2f-e809fc081822'::uuid,
    '2f35f8a7-93ea-4028-a271-df58dce6bbd2'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.4693765, 31.6057771),
        ST_MakePoint(104.4693726, 31.6057118)
    ), 4326),
    'unclassified',
    7.27,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '5e476933-0f4f-4c6e-8aa6-07a2510b0b9a'::uuid,
    '53ac603b-a60d-42a3-ae21-bd8b81f87618'::uuid,
    'd7fc0f0c-0a8a-4053-94be-d819c49e5cf2'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.2882924, 31.2488686),
        ST_MakePoint(104.2971071, 31.2505329)
    ), 4326),
    'unclassified',
    858.14,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    'ac397cd5-9495-43d5-879d-ec4065227d12'::uuid,
    'bb0f3610-3b97-4bc2-8660-c92312c5f782'::uuid,
    '5bd2a2f9-a577-4606-a917-ddab36a7226c'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.2946358, 31.2917184),
        ST_MakePoint(104.2904745, 31.2990143)
    ), 4326),
    'unclassified',
    902.49,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    'b8372b31-3f24-409a-be0d-64b7bc40c081'::uuid,
    '0338b4c6-d388-485e-a423-21891df83287'::uuid,
    'ac2bb229-ed18-44e6-a2d5-746a06ef1e4f'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(103.4997564, 31.3643106),
        ST_MakePoint(103.5002682, 31.3652384)
    ), 4326),
    'unclassified',
    114.04,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '45a08331-c1c6-4b5a-b2ab-b7e91b6a4004'::uuid,
    '049e5727-6728-40c1-a83c-ccc3074125fb'::uuid,
    '1282296c-3850-4818-aeb9-cd61b1846a2d'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.1976346, 31.3625601),
        ST_MakePoint(104.2080231, 31.3683298)
    ), 4326),
    'unclassified',
    1176.63,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    'ec3b7cae-bde2-4034-8907-d4e4b2a00ab7'::uuid,
    'c346c318-54c3-49e3-a9cd-62a9cf2dcffa'::uuid,
    'e3071a36-f781-491b-bf61-1438982facc4'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(103.5782033, 31.480027),
        ST_MakePoint(103.5766736, 31.4747036)
    ), 4326),
    'unclassified',
    609.45,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    'db99818f-42c6-427c-9758-0ea3d8629a79'::uuid,
    '3321d8f0-045b-41f6-a3fe-14fd4f823975'::uuid,
    '2902807c-9f8c-44df-9987-d18aa384c712'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.3194142, 31.5986222),
        ST_MakePoint(104.3255046, 31.5903835)
    ), 4326),
    'unclassified',
    1082.58,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    'ddbdb185-404f-4eb2-8bfd-3e48ab89eb81'::uuid,
    'a44b05dd-a14f-4a00-b637-c51124b9e0f2'::uuid,
    '19d9184b-2b18-4bba-a707-f8ebc33bd008'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.4666402, 31.6110825),
        ST_MakePoint(104.4655604, 31.6106216)
    ), 4326),
    'unclassified',
    114.38,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    'f6a4e8e8-dc77-445f-aeab-43d3f2f8ba70'::uuid,
    'f6340981-f42c-44e6-a472-29c79cc1d3f7'::uuid,
    'cf3fd3bc-6465-4944-a137-5f53959a29f3'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.4623464, 31.6092478),
        ST_MakePoint(104.461597, 31.6105424)
    ), 4326),
    'unclassified',
    160.50,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '44911751-5cf2-4358-aa15-13e42d45f2f7'::uuid,
    '972a3daa-523c-4523-9427-38c075e61cd5'::uuid,
    'aff1ddc1-ddbf-438d-af67-dfda04f75a78'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.275162, 31.241518),
        ST_MakePoint(104.2771217, 31.2473811)
    ), 4326),
    'unclassified',
    678.04,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    'a291a306-4af3-4090-bda9-0821ac2e3ca6'::uuid,
    '699d28e2-c245-4f3a-b01b-7b3c47f4fdee'::uuid,
    'ad5c260a-28f4-4dd4-b1e8-a91a49d85c8e'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.2712655, 31.248664),
        ST_MakePoint(104.266993, 31.2484973)
    ), 4326),
    'unclassified',
    406.58,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '3c6214b1-3b80-4ad3-b02b-97ba1e3e9d26'::uuid,
    'd3b13fca-06f3-408a-a86d-c5f34d9eb176'::uuid,
    '686aebdb-735e-4093-8c35-7bb2f0001699'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.2274988, 31.2710821),
        ST_MakePoint(104.2208866, 31.2675044)
    ), 4326),
    'unclassified',
    743.77,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '67911e1b-7c6a-49a7-bf23-278846b57e80'::uuid,
    '6e69b3c6-d905-44b5-b9b0-a5ce4659087e'::uuid,
    '5349fccc-783b-4708-b691-3c2202192946'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.3051428, 31.3280515),
        ST_MakePoint(104.300645, 31.3326491)
    ), 4326),
    'unclassified',
    666.23,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '64703350-b73d-41d6-95e9-41db8b3e185c'::uuid,
    '99319c82-d431-48c0-885b-4545784205e5'::uuid,
    '3ee84061-5311-4d3f-ad51-cb7365b82b5a'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.3441694, 31.511633),
        ST_MakePoint(104.3339683, 31.5083873)
    ), 4326),
    'unclassified',
    1032.21,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    'ec9ecf02-b76c-499d-895d-39306313f151'::uuid,
    '4aa3c93d-9a7b-4d9a-9b71-1c33fe899faf'::uuid,
    '73d12f1b-8b1d-4cc7-aafc-5ef68549172e'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.276025, 31.2638715),
        ST_MakePoint(104.2713004, 31.2623946)
    ), 4326),
    'unclassified',
    478.15,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    'e1b16c7a-a9a5-4ece-9a8b-83830e779802'::uuid,
    '61579a5d-3e69-42b5-8a55-ea20f1b2da86'::uuid,
    '1bfd40be-18ba-4c31-bdd4-3c3d45bb970c'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.4295809, 31.2261281),
        ST_MakePoint(104.4276411, 31.2279197)
    ), 4326),
    'unclassified',
    271.49,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '7ea119bb-537d-4ca0-a61e-9c70db4a7053'::uuid,
    '99319c82-d431-48c0-885b-4545784205e5'::uuid,
    '1c80feae-cfa8-468e-b34e-991445d95fe9'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.3441694, 31.511633),
        ST_MakePoint(104.3454087, 31.5114227)
    ), 4326),
    'unclassified',
    119.79,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '013a1552-083c-4ecd-b9fb-ce31347b6584'::uuid,
    'bb0f3610-3b97-4bc2-8660-c92312c5f782'::uuid,
    'b9b72c2b-1c54-446e-a975-7ef1158fbcac'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.2946358, 31.2917184),
        ST_MakePoint(104.2917192, 31.2957262)
    ), 4326),
    'unclassified',
    524.79,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    'e92f316f-3ff3-43b3-818b-2a4cb99c8f6c'::uuid,
    'e53baea4-cdab-4d97-8eeb-ffeba8fa31d0'::uuid,
    'b6c7c571-4d6f-4866-8e22-75cbfa12c2ca'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(103.9543157, 31.73601),
        ST_MakePoint(103.9498063, 31.7324873)
    ), 4326),
    'unclassified',
    579.05,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '2d133f8d-bad6-49fa-a150-01d259c4c01c'::uuid,
    'a4dac3ef-dd11-4c7e-8777-80b2afbf9dad'::uuid,
    '54454f4c-4f80-461a-8103-6d93a25cd1af'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.1128504, 31.5304825),
        ST_MakePoint(104.1112183, 31.5181009)
    ), 4326),
    'unclassified',
    1385.43,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '6f933ac5-4832-4805-b43b-8586bc668575'::uuid,
    'a4dac3ef-dd11-4c7e-8777-80b2afbf9dad'::uuid,
    '940d233f-bb83-4e8f-90d3-ce1c8cfc58ae'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.1128504, 31.5304825),
        ST_MakePoint(104.111878, 31.5183259)
    ), 4326),
    'unclassified',
    1354.89,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    'af196790-0817-4bc3-92c7-fac61939f624'::uuid,
    'c007bc3a-54f9-4d2d-a2d9-8b224759df7d'::uuid,
    'fbc0634f-683d-49b5-afbb-ffffe282dfc0'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.3578522, 31.3382176),
        ST_MakePoint(104.3540032, 31.3382722)
    ), 4326),
    'unclassified',
    365.60,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '48c6e3e1-5471-4b0f-8874-9a9a1d4aacb9'::uuid,
    '38dfbdd1-ca4d-4d9c-8622-9d9b45337064'::uuid,
    'e4aad81b-1b22-4bfa-b57f-d752a14ab620'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.2052633, 31.4010688),
        ST_MakePoint(104.2035305, 31.4010115)
    ), 4326),
    'unclassified',
    164.58,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    'f3392cbb-2f1a-40ba-bd24-d9276dd0ed9b'::uuid,
    '2d450746-932a-4205-9faf-653fa12962a4'::uuid,
    '2d9978d8-9a7c-49de-82b1-de303d919e50'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.3153689, 31.2688623),
        ST_MakePoint(104.3197526, 31.2577522)
    ), 4326),
    'unclassified',
    1303.76,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    'f275cfdd-c823-467a-82ed-2a538841ebcf'::uuid,
    'c007bc3a-54f9-4d2d-a2d9-8b224759df7d'::uuid,
    'c41976db-c62d-4ad3-ba82-1f4a5b7db686'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.3578522, 31.3382176),
        ST_MakePoint(104.3505639, 31.3459221)
    ), 4326),
    'unclassified',
    1101.37,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '3fbf57d3-556a-4bbe-ad83-b5b8b9a81337'::uuid,
    '41a27c6f-8f15-4409-8ddf-7ad56bc9365a'::uuid,
    'a7102220-a308-4464-b64a-0e02b758e94e'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(103.3831295, 31.5652698),
        ST_MakePoint(103.3830638, 31.565306)
    ), 4326),
    'unclassified',
    7.41,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '6c0d3cee-be50-487b-9b90-0a09157dc3b4'::uuid,
    'a6313a91-08d3-47df-8a4b-92a13cf86268'::uuid,
    'f0d857b4-41b9-44d7-96b3-e0a0e3392ffa'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.2916528, 31.3189735),
        ST_MakePoint(104.2967416, 31.3167979)
    ), 4326),
    'unclassified',
    540.56,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    'd0c9911f-d074-4bdd-842c-4b3b9892bd7d'::uuid,
    '1fb0a0c6-e1e4-4edb-97ea-89dca30e0e99'::uuid,
    '5765ab49-150a-4a22-9e98-ac73fccfdec1'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.0924291, 31.3202131),
        ST_MakePoint(104.0797477, 31.3135957)
    ), 4326),
    'unclassified',
    1411.61,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '4720e47e-3437-4a2e-b631-97d7690de65d'::uuid,
    'ed3ee5cf-3d14-46cf-aab3-7eaf715aadd0'::uuid,
    '458912b1-3ae8-4ec3-afcc-1836a45d4670'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.4509643, 31.8232328),
        ST_MakePoint(104.4518548, 31.8230641)
    ), 4326),
    'unclassified',
    86.20,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '7659af3f-7c5c-40d0-a533-89bf4a39d74f'::uuid,
    '21ae32eb-e9de-4e9a-be3b-c536f0cf27b9'::uuid,
    '8b717813-9637-4628-a7b3-982c406f57b7'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(103.9398713, 31.735454),
        ST_MakePoint(103.9449869, 31.7291555)
    ), 4326),
    'unclassified',
    851.21,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    'b4979f6c-06e7-47ef-b4d6-e1def1b96f8e'::uuid,
    'fbbb165d-7cac-4769-8523-b5079d195066'::uuid,
    '226e0fcf-24af-4920-bdae-c35629f19984'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(103.7273813, 31.5778243),
        ST_MakePoint(103.731052, 31.5756146)
    ), 4326),
    'unclassified',
    425.78,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '14a0ad5f-41af-4678-b546-ccdbf66eff71'::uuid,
    'dcdd217d-31f9-4fa1-a1ae-240cfc0de606'::uuid,
    'd5590091-34ba-4df1-aa57-05a14b09273e'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(103.8200579, 31.7619785),
        ST_MakePoint(103.8249304, 31.7579054)
    ), 4326),
    'unclassified',
    646.02,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '728345cb-2376-4049-825b-7fbf29f8f8de'::uuid,
    '1fb0a0c6-e1e4-4edb-97ea-89dca30e0e99'::uuid,
    '285bc2c3-383e-4bdb-9b38-31cc86a52a3d'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.0924291, 31.3202131),
        ST_MakePoint(104.0939681, 31.3133847)
    ), 4326),
    'unclassified',
    773.23,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '07933649-3861-4433-8c8e-af09139ded6b'::uuid,
    'a6ea77b5-29c2-4df6-b9dd-e79a328145ec'::uuid,
    'a3be751d-0e94-40d5-aa5f-a1e2455efeb1'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.4177699, 31.6421477),
        ST_MakePoint(104.4133278, 31.6419556)
    ), 4326),
    'unclassified',
    421.05,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    'e89044d2-c2d2-4fed-8387-46af0c0767f4'::uuid,
    '07ffa895-24cd-4a0f-b968-2ae892a44d74'::uuid,
    '4b8e7087-e491-47ef-8db5-83dcb784eb5a'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.4259244, 31.2215882),
        ST_MakePoint(104.4161129, 31.223433)
    ), 4326),
    'unclassified',
    955.26,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    'f7cf65b3-c47c-4dbf-bd8c-c379d472092f'::uuid,
    'edc477f0-4d62-423a-a417-b4e64ff1e436'::uuid,
    'f52d8ff1-411e-41f2-8bcf-1ff3cc6be8a4'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.2866658, 31.3144903),
        ST_MakePoint(104.28868, 31.3161426)
    ), 4326),
    'unclassified',
    265.27,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '15bd4c90-0ebf-4355-b66b-da980c702d48'::uuid,
    '642ec80b-e261-4943-ba7a-7a451a2a0bcb'::uuid,
    '4e3f5015-2256-47a2-a24e-5a42c3c6758a'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.1927678, 31.3446537),
        ST_MakePoint(104.1969873, 31.3537687)
    ), 4326),
    'unclassified',
    1089.87,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '4a302698-5928-495f-9f90-5cf8c8b13c40'::uuid,
    '0177010f-1e7e-475a-9f40-6765cef6a522'::uuid,
    'bb11e0f9-76c1-4d0a-8939-303d8c2ec515'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.4565967, 31.6820539),
        ST_MakePoint(104.4554275, 31.6848386)
    ), 4326),
    'unclassified',
    328.82,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    'b3e814e4-e328-4079-b904-6bc9d4ea37dc'::uuid,
    '354830ea-458a-4aba-a81c-588ea889f774'::uuid,
    '96d63219-cdd2-4e26-9db7-bb833ddddf3d'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.4529523, 31.6172055),
        ST_MakePoint(104.4523845, 31.6195334)
    ), 4326),
    'unclassified',
    264.38,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    'fad9fa02-43fb-4b3a-bd72-0d3201a63e49'::uuid,
    '9a6391bc-c182-44ce-b10a-43c711af346d'::uuid,
    '7222d0e6-4a7a-4e30-b9b1-db1acd225ac7'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.3429455, 31.2078474),
        ST_MakePoint(104.349488, 31.2127641)
    ), 4326),
    'unclassified',
    828.27,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    'd570c75b-7f13-404a-9a9d-7c834fd507b3'::uuid,
    '8ec6d895-f7b3-486b-9789-0fa96ac37e72'::uuid,
    'be529f73-33bf-4083-84e4-6571230a3828'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.4019417, 31.870495),
        ST_MakePoint(104.4057123, 31.8793121)
    ), 4326),
    'unclassified',
    1043.07,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '7e048022-f8ac-4ea2-b1ee-0a3860cb51ee'::uuid,
    '905d34e9-75f4-43ba-bfeb-d3abcf9eb573'::uuid,
    'fb286249-ee7e-4cfa-84f7-d2d313cabd8c'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.339075, 31.2158777),
        ST_MakePoint(104.3420133, 31.2156757)
    ), 4326),
    'unclassified',
    280.32,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '1b7e0c5d-2ce5-4615-9432-75d196efdcaf'::uuid,
    '230eafc2-b7d8-472c-b7b1-05da5d16e455'::uuid,
    '9c52b50f-a44a-400d-9d24-b9b54fd6f8a1'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.3115743, 31.296245),
        ST_MakePoint(104.3132659, 31.2914913)
    ), 4326),
    'unclassified',
    552.48,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '0058e2b8-3cac-45e3-936d-b3ad7350a4af'::uuid,
    'cd457140-ff22-48d1-9e38-f0616e890319'::uuid,
    'b7dc7278-da35-4996-9ae6-b58999360698'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.0745341, 31.3216759),
        ST_MakePoint(104.0847109, 31.3297415)
    ), 4326),
    'unclassified',
    1318.62,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '0ea569f8-2ab3-43c8-981c-ccf449b6424c'::uuid,
    '53d22df3-2730-479e-967d-832279a52acc'::uuid,
    '416edde8-201e-44d9-a312-e64c441840f3'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.0091401, 31.3783211),
        ST_MakePoint(104.0229622, 31.3825989)
    ), 4326),
    'unclassified',
    1395.69,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '7ccc30cb-0530-46b4-a16f-96710a07cc89'::uuid,
    'd3b13fca-06f3-408a-a86d-c5f34d9eb176'::uuid,
    'b16d3218-a305-497d-8bd4-4c44b8bbc0c3'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.2274988, 31.2710821),
        ST_MakePoint(104.2338234, 31.2770425)
    ), 4326),
    'unclassified',
    894.73,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '66e7590e-5523-4a4f-86ce-a95aed106806'::uuid,
    '8db09490-33e5-459e-ad43-a48888f51534'::uuid,
    '75086403-f001-4788-b578-8b6def1cab46'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(103.3602385, 31.5748616),
        ST_MakePoint(103.3571707, 31.571541)
    ), 4326),
    'unclassified',
    469.89,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    'dd416f09-2a9f-4167-8376-7c243e77064f'::uuid,
    '98bbc7c2-1beb-48e5-94fc-e9dc4470c489'::uuid,
    '3c970f00-6b6d-44f5-85f0-a4ed1e376116'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.324525, 31.3042722),
        ST_MakePoint(104.3245418, 31.3072133)
    ), 4326),
    'unclassified',
    327.04,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '55673295-1f35-4799-856f-9568b3f9623d'::uuid,
    'e53baea4-cdab-4d97-8eeb-ffeba8fa31d0'::uuid,
    '62432853-d969-4bd6-954d-5ec5eb1ffe80'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(103.9543157, 31.73601),
        ST_MakePoint(103.9603146, 31.7372927)
    ), 4326),
    'unclassified',
    584.96,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    'b2747a79-c0dd-4b30-ac13-7487e1ec31c5'::uuid,
    'e53baea4-cdab-4d97-8eeb-ffeba8fa31d0'::uuid,
    '4df44723-07ee-48cb-8fc5-253bf4539b25'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(103.9543157, 31.73601),
        ST_MakePoint(103.9568279, 31.7392321)
    ), 4326),
    'unclassified',
    429.89,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '96dfb5d0-968c-479e-ac65-c5baeafc99ed'::uuid,
    'c14d1525-3809-473d-a50f-f14f13abc8c8'::uuid,
    '309d38e8-7b2e-4f71-a72b-8a2a406e2c3c'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(103.582392, 31.4812829),
        ST_MakePoint(103.5867543, 31.4888263)
    ), 4326),
    'unclassified',
    935.24,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '82998132-c618-4cca-91ef-46d651719b83'::uuid,
    'b8cdc20c-58b1-41c7-a598-bd89548c478f'::uuid,
    '0f26d846-cfbc-4f81-a88f-5a84d8082ae4'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(103.5152354, 31.3848134),
        ST_MakePoint(103.5061801, 31.3821469)
    ), 4326),
    'unclassified',
    909.29,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    'ca77f5bb-5ae0-4dd4-9b0a-cd1c95f0def0'::uuid,
    'a9293702-64c3-4684-ac7a-fd903d65c10d'::uuid,
    '5249c43c-ed79-4a7b-a2ce-04dc37183962'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.1870983, 31.4459963),
        ST_MakePoint(104.1768908, 31.4444264)
    ), 4326),
    'unclassified',
    983.94,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '43c69984-76bf-41b9-a142-5068bb90cd6a'::uuid,
    '7dd5d680-e378-4352-87a4-94459e7f2103'::uuid,
    '12fa5eee-7f00-4aca-a193-a241f2c970ad'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(103.9110447, 31.2241353),
        ST_MakePoint(103.9141282, 31.2152032)
    ), 4326),
    'unclassified',
    1035.58,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '01008ac4-f9c0-4fab-812e-18adb24b23a5'::uuid,
    '7b460380-d786-4b37-9e54-9202c70631fa'::uuid,
    '9a93fee1-15a5-4bd9-9276-d71fc4b0fcb4'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.394616, 31.2224874),
        ST_MakePoint(104.3881385, 31.2208752)
    ), 4326),
    'unclassified',
    641.51,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '5039d25f-8666-44f0-9f19-306a70e5930c'::uuid,
    'c7229b2c-0cb8-4661-a055-375d0e925370'::uuid,
    '140acba8-687c-4f3b-a7e7-fad8ba9a79ce'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.4054788, 31.2420943),
        ST_MakePoint(104.4072337, 31.244544)
    ), 4326),
    'unclassified',
    319.43,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '04c59bc9-dad1-4bb8-b774-a5ec5eb32753'::uuid,
    'ddfeea3e-a24c-4ce4-b9be-7043229a63a5'::uuid,
    '731cf71e-3f88-46c8-b279-629eec39e738'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.1955107, 31.2820535),
        ST_MakePoint(104.188934, 31.282732)
    ), 4326),
    'unclassified',
    629.52,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    'd562541e-d3ab-4f49-b67b-72fd6e5b6280'::uuid,
    'debc7ad8-1e7e-4a53-83af-bcbe66af18c8'::uuid,
    '9b29b5f7-3ec8-4bc8-a6d1-2eba1fb0af92'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.1708948, 31.4493429),
        ST_MakePoint(104.1675774, 31.4464403)
    ), 4326),
    'unclassified',
    450.78,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '7cfff46a-11d2-4fd3-a272-3b9925a4b8e0'::uuid,
    '82002ec9-bf72-4559-a98d-93398b327d84'::uuid,
    '20e4d401-79c9-4527-8b52-fc796f7bb439'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(103.9172916, 31.2246032),
        ST_MakePoint(103.9143616, 31.2348943)
    ), 4326),
    'unclassified',
    1177.74,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    'ae484767-cb6d-4513-817b-c076c02ec7fe'::uuid,
    '07ffa895-24cd-4a0f-b968-2ae892a44d74'::uuid,
    '21ec4c95-423f-4a0e-86fc-7899d4cab1c6'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.4259244, 31.2215882),
        ST_MakePoint(104.4139886, 31.2231404)
    ), 4326),
    'unclassified',
    1148.02,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    'b9b464a7-4019-4eb7-8c94-30428311e1ea'::uuid,
    '1a7234af-3e67-4905-afbd-1fe00a580671'::uuid,
    '766d6934-79eb-40f6-b4c5-33fc6c8da87f'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.3421346, 31.3461457),
        ST_MakePoint(104.3514398, 31.334489)
    ), 4326),
    'unclassified',
    1568.76,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    'c0726465-745b-4424-9728-4937a330e4fa'::uuid,
    'd520f332-a0f0-4319-af8f-56ed2ae4055a'::uuid,
    '95ca6455-2307-4659-8f71-4bd1f87cb383'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.3213458, 31.2704186),
        ST_MakePoint(104.3230459, 31.2729414)
    ), 4326),
    'unclassified',
    323.73,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO operational_v2.road_edges_v2 (
    id, from_node_id, to_node_id, geometry,
    road_type, length_m, max_speed_kmh, is_accessible
) VALUES (
    '7df767e7-0fa2-4d02-bcd5-fa4b4589e0c5'::uuid,
    'd520f332-a0f0-4319-af8f-56ed2ae4055a'::uuid,
    '17119e81-2a44-4d19-be1d-15ee37f5a471'::uuid,
    ST_SetSRID(ST_MakeLine(
        ST_MakePoint(104.3213458, 31.2704186),
        ST_MakePoint(104.3177244, 31.2743188)
    ), 4326),
    'unclassified',
    553.66,
    30,
    true
) ON CONFLICT (id) DO NOTHING;

COMMIT;
