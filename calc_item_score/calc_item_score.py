#!/usr/bin/env python
# coding: utf-8

# In[1]:


import json
import matplotlib.pyplot as plt
import random
import copy
import easyocr
import os


# In[2]:


def load_roles_weight(input_path=None):
    if input_path is None:
        with open("roles_weight.json", "r", encoding='utf-8') as f:
            roles_weight = json.load(f)
    
    return roles_weight

# TEST
# print(load_roles_weight())


# In[4]:


def load_attrs_step(input_path=None):
    if input_path is None:
        with open("attrs_step.json", "r", encoding='utf-8') as f:
            attrs_step = json.load(f)
    
    return attrs_step

# TEST
# print(load_attrs_step())


# In[6]:


def load_attrs_weight(input_path=None):
    if input_path is None:
        with open("attrs_weight.json", "r", encoding='utf-8') as f:
            attrs_weight = json.load(f)
    
    return attrs_weight

# TEST
# print(load_attrs_weight())


# In[8]:

def load_input_param(input_path=None):
    if input_path is None:
        with open("input_param.json", "r", encoding='utf-8') as f:
            input_param = json.load(f)
    
    return input_param

# TEST
# print(load_input_param())


# In[8]:


def load_attrs_choice(input_path=None):
    if input_path is None:
        with open("attrs_choice.json", "r", encoding='utf-8') as f:
            attrs_choice = json.load(f)
    
    return attrs_choice

# TEST
# print(load_attrs_choice())


# In[8]:


def check_valid(item):
    item_minor_attrs = [i for i in item['minor_attr'] if item['minor_attr'][i] > 0]
    if item['major_attr'] in item_minor_attrs:
        return False
    elif len(item_minor_attrs) > 4 or len(item_minor_attrs) < 3:
        return False
    elif item['level'] > 20 or item['level'] < 0:
        return False
    else:
        return True

# TEST
# item = load_input_param()["item"]
# print(check_valid(item))


# In[8]:


def upgrade_once(item, attrs_step=None, attrs_choice=None):
    if attrs_step is None:
        attrs_step = load_attrs_step()
    if attrs_choice is None:
        attrs_choice = load_attrs_choice()

    item_minor_attrs = [i for i in item['minor_attr'] if item['minor_attr'][i] > 0]
    if len(item_minor_attrs) == 3:
        for i in item_minor_attrs:
            attrs_choice[i] = 0
        attrs_choice[item['major_attr']] = 0
        upgrade_attr = random.choices(list(attrs_choice.keys()), list(attrs_choice.values()))[0]
    elif len(item_minor_attrs) == 4:
        upgrade_attr = random.choice(item_minor_attrs)
    
    upgrade_value = random.choice(attrs_step[upgrade_attr])

    item['minor_attr'][upgrade_attr] += upgrade_value
    item['level'] = (item['level']//4 + 1) * 4

    return item

# TEST
# item = load_input_param()["item"]
# print(upgrade_once(item))


# In[8]:


def upgrade(item, level=20, attrs_step=None, attrs_choice=None):
    if attrs_step is None:
        attrs_step = load_attrs_step()

    if check_valid(item):
        upgrade_cnt = level//4 - item['level']//4

        for i in range(upgrade_cnt):
            item = upgrade_once(item, attrs_step, attrs_choice)
        
        item['level'] = level
    else:
        raise Exception("item param invalid")
    
    return item

# TEST
# item = load_input_param()["item"]
# print(upgrade(item))


# In[12]:


def trans_role_weight(role_weight):
    role_weight['小生命'] = role_weight['生命']
    role_weight['小攻击'] = role_weight['攻击']
    role_weight['小防御'] = role_weight['防御']
    role_weight['大生命'] = role_weight['生命']
    role_weight['大攻击'] = role_weight['攻击']
    role_weight['大防御'] = role_weight['防御']

    return role_weight

# TEST
# print(trans_role_weight(load_roles_weight()['夜兰']))


# In[12]:


def calc_score(item, role, attrs_weight=None, roles_weight=None):
    if attrs_weight is None:
        attrs_weight = load_attrs_weight()
    if roles_weight is None:
        roles_weight = load_roles_weight()

    role_weight = trans_role_weight(roles_weight[role])

    socre = 0
    for attr in item['minor_attr']:
        if item['minor_attr'][attr] > 0:
            socre += item['minor_attr'][attr] * attrs_weight[attr] * role_weight[attr]

    return socre/100

# TEST
# item = load_input_param()["item"]
# print(calc_score(item, '夜兰'))


# In[26]:


def calc_score_roles(input_param=None, roles_weight=None, attrs_weight=None, attrs_step=None, attrs_choice=None):
    if input_param is None:
        input_param = load_input_param()
    if attrs_weight is None:
        attrs_weight = load_attrs_weight()
    if roles_weight is None:
        roles_weight = load_roles_weight()
    if attrs_step is None:
        attrs_step = load_attrs_step()
    if attrs_choice is None:
        attrs_choice = load_attrs_choice()

    roles = input_param["roles"]
    init_item = input_param["item"]
    scores2 = []

    for role in roles:
        item = copy.deepcopy(init_item)
        init_score = calc_score(item, role, attrs_weight, roles_weight)

        scores = []
        for cnt in range(10000):
            item = copy.deepcopy(init_item)
            item = upgrade(item, 20, attrs_step, attrs_choice)
            scores.append(calc_score(item, role, attrs_weight, roles_weight))
        scores2.append(scores)

    plt.rcParams['font.sans-serif'] = ['SimHei']
    plt.boxplot(scores2)
    plt.xticks([i for i in range(1, 1+len(roles))], labels = roles) 

    return plt

# TEST
# input_param = load_input_param()
# print(calc_score_roles())


# In[ ]:


def ocr_item(input_param=None):
    reader = easyocr.Reader(['ch_sim'], gpu = False) # need to run only once to load model into memory
    result = reader.readtext(input_param["item_path"], detail = 0)
    print(result)
    return result

# TEST
# print(ocr_item(load_input_param()))


# In[1]:


# parse result
def parse_result(result):
    item = {}
    if result[1] == "生之花":
        item["position"] = 1
        item["major_attr"] = "小生命"
    elif result[1] == "死之羽":
        item["position"] = 2
        item["major_attr"] = "小攻击"
    elif result[1] == "时之沙":
        item["position"] = 3
        if result[2] == "生命值":
            item["major_attr"] = "大生命"
        elif result[2] == "防御力":
            item["major_attr"] = "大防御"
        elif result[2] == "攻击力":
            item["major_attr"] = "大攻击"
        elif result[2] == "元素精通":
            item["major_attr"] = "精通"
        elif result[2] == "元素充能效率":
            item["major_attr"] = "充能"
    elif result[1] == "空之杯":
        item["position"] = 4
        if result[2] == "生命值":
            item["major_attr"] = "大生命"
        elif result[2] == "防御力":
            item["major_attr"] = "大防御"
        elif result[2] == "攻击力":
            item["major_attr"] = "大攻击"
        elif result[2] == "元素精通":
            item["major_attr"] = "精通"
        elif result[2] == "物理伤害加成":
            item["major_attr"] = "物伤"
        elif result[2] == "火元素伤害加成":
            item["major_attr"] = "火伤"
        elif result[2] == "水元素伤害加成":
            item["major_attr"] = "水伤"
        elif result[2] == "草元素伤害加成":
            item["major_attr"] = "草伤"
        elif result[2] == "雷元素伤害加成":
            item["major_attr"] = "雷伤"
        elif result[2] == "风元素伤害加成":
            item["major_attr"] = "风伤"
        elif result[2] == "冰元素伤害加成":
            item["major_attr"] = "冰伤"
        elif result[2] == "岩元素伤害加成":
            item["major_attr"] = "岩伤"
    elif result[1] == "理之冠":
        item["position"] = 5
        if result[2] == "生命值":
            item["major_attr"] = "大生命"
        elif result[2] == "防御力":
            item["major_attr"] = "大防御"
        elif result[2] == "攻击力":
            item["major_attr"] = "大攻击"
        elif result[2] == "元素精通":
            item["major_attr"] = "精通"
        elif result[2] == "暴击率":
            item["major_attr"] = "暴击"
        elif result[2] == "暴击伤害":
            item["major_attr"] = "爆伤"
    item["level"] = int(result[4])
    item["minor_attr"] = {
        "小生命": 0, 
        "小攻击": 0, 
        "小防御": 0, 
        "精通"  : 0, 
        "充能"  : 0, 
        "大生命": 0, 
        "大攻击": 0,
        "大防御": 0, 
        "暴击"  : 0, 
        "爆伤"  : 0
    }
    for i in result[5:]:
        i_parse = i.split('+')
        # print(i_parse)
        if i_parse[0] == "生命值":
            if "%" in i_parse[1]:
                item["minor_attr"]["大生命"] = float(i_parse[1][:-1])
            else:
                item["minor_attr"]["小生命"] = float(i_parse[1])
        elif i_parse[0] == "防御力":
            if "%" in i_parse[1]:
                item["minor_attr"]["大防御"] = float(i_parse[1][:-1])
            else:
                item["minor_attr"]["小防御"] = float(i_parse[1])
        elif i_parse[0] == "攻击力":
            if "%" in i_parse[1]:
                item["minor_attr"]["大攻击"] = float(i_parse[1][:-1])
            else:
                item["minor_attr"]["小攻击"] = float(i_parse[1])
        elif i_parse[0] == "元素精通":
            item["minor_attr"]["精通"] = float(i_parse[1])
        elif i_parse[0] == "元素充能效率":
            item["minor_attr"]["充能"] = float(i_parse[1][:-1])
        elif i_parse[0] == "暴击率":
            item["minor_attr"]["暴击"] = float(i_parse[1][:-1])
        elif i_parse[0] == "暴击伤害":
            item["minor_attr"]["爆伤"] = float(i_parse[1][:-1])
    print(item)
    return item

# TEST
# print(parse_result(result))


# In[ ]:


if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.realpath(__file__)))
    input_param = load_input_param()
    if "item" not in input_param:
        item = parse_result(ocr_item(input_param))
        input_param["item"] = item
    plt = calc_score_roles(input_param)
    plt.show()


# In[ ]: