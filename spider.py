#!/usr/bin/python
# -*- coding: utf-8 -*-

import urllib2
import re
from urllib import unquote
from pymongo import MongoClient
import threading
import random
import json
import time
from multiprocessing import Pool
import thread

class XiangHaRecipe(object):
	"""docstring for XiangHaRecipe"""
	def __init__(self):
		super(XiangHaRecipe, self).__init__()
		self.baseURL = 'https://www.xiangha.com/caipu/'
		self.user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.99 Safari/537.36'
		self.headers = {'User-Agent' : self.user_agent}
		self.client = MongoClient('localhost',27017)
		self.mydb = self.client.meals

	def scapyFunction(self,url):
		try:
			request = urllib2.Request(url, headers = self.headers)
			response = urllib2.urlopen(request)
			html = response.read()
			return html
		except Exception as e:
			if hasattr(e, 'reason'):
				print u"链接失败，原因：", e.reason, url
			return None

	# 获取三餐的列表
	def mealsList(self,url,meal = ''):
		# url = self.baseURL + meal + '/hot-' + str(page)
		print url
		mealHtml = self.scapyFunction(url)
		if not mealHtml:
			return None
		meal_pattern = re.compile('<li><a class="pic (.*?)" title="(.*?)" href="(.*?)".*?><img alt="(.*?)" src="(.*?)" height="(.*?)" width="(.*?)".*?<p class="info"><span>(.*?)浏览</span>(.*?)收藏</p>.*?</li>', re.S)
		recipeList = re.findall(meal_pattern, mealHtml)
		mealRecipes = []
		for recipe in recipeList:
			recipe_isvideo = len(recipe[0].strip()) != 0
			recipe_id = recipe[2].strip().split('/')[-1].split('.')[0]
			recipeMsg = {
				'recipe_isvideo' : recipe_isvideo,
				'recipe_id' : recipe_id,
				'recipe_type' : meal,
				'recipe_name' : recipe[1].strip(),
				'recipe_href' : recipe[2].strip(),
				'recipe_imgalt' : recipe[3].strip(),
				'recipe_imgsrc' : recipe[4].strip(),
				'recipe_img_h' :recipe[5].strip(),
				'recipe_img_w' :recipe[6].strip(),
				'recipe_browse' : recipe[7].strip(),
				'recipe_collection' :recipe[8].strip()
			}
			mealRecipes.append(recipeMsg)

		# if meal == 'c-wancan':
		# 	self.mydb.c_wancan.insert_many(mealRecipes)
		# elif meal == 'c-zaocan':
		# 	self.mydb.c_zaocan.insert_many(mealRecipes)
		# elif meal == 'c-zhongcan':
		# 	self.mydb.c_zhongcan.insert_many(mealRecipes)
		# else: 
		if mealRecipes is None:
			return None
		else:
			self.mydb[meal].insert_many(mealRecipes)	
			return mealRecipes


	# 根据菜谱的url获取菜谱详细的步骤
	def recipeSteps(self, recipe_url):
		recipe_id = recipe_url.split('/')[-1].split('.')[0]
		recipe = {'recipe_id' : recipe_id}
		recipeHtml = self.scapyFunction(recipe_url)
		try:
			# 获取视频
			video_pattern = re.compile('<video id="xhPlayer" poster="(.*?)".*?<source src="(.*?)".*?></source></video>', re.S)
			videomatch = re.findall(video_pattern, recipeHtml)

			recipe['video_poster'] = videomatch[0][0] if len(videomatch) > 0 else ''
			recipe['video_src'] = videomatch[0][1] if len(videomatch) > 0 else ''
		except Exception as e:
			if hasattr(e, 'reason'):
				print e.reason,recipe_url
			else:
				print 'recipeSteps---获取视频失败',recipe_url
		
		try:
			# 获取图片封面
			img_pattern = re.compile('<div class="pic"><img src="(.*?)".*?/></div>',re.S)
			imgmatch = re.findall(img_pattern, recipeHtml)
			recipe['recipe_cover'] = imgmatch[0] if len(imgmatch) > 0 else ''
		except Exception as e:
			if hasattr(e, 'reason'):
				print e.reason,recipe_url
			else:
				print 'recipeSteps---获取封面失败',recipe_url

		# 获取菜谱食材列表
		pattern = re.compile('<div class="cell">(.*?)<span>(.*?)</span>(.*?)</div>', re.S)

		shicaimatch = re.findall(pattern, recipeHtml)

		shicai_pattern = re.compile('.*?href="(.*?)".*?', re.S)
		xiangke_pattern = re.compile('.*?href="(.*?)".*?',re.S)

		shicai_all = []
		for item in shicaimatch:
			shicai = {}
			if 'href=' in item[0]:
				shicai_detail = re.findall(shicai_pattern, item[0].strip()) # 食材详情链接
				shicai_name = unquote(shicai_detail[0].split('/')[-1])	# 食材名
				shicai['shicai_name'] = shicai_name
				shicai['shicai_detail'] = shicai_detail[0].strip()
			else:
				# 食材详情不存在，直接输出食材名
				shicai_name = item[0].strip()
				shicai['shicai_name'] = shicai_name
				shicai['shicai_detail'] = ''	
			# 食材分量
			shicai_fenliang = item[1].strip()
			shicai['shicai_fenliang'] = shicai_fenliang

			if 'href=' in item[2]:
				shic_xiangke = re.findall(xiangke_pattern, item[2].strip())
				# 食物相克链接
				shicai['shic_xiangke'] = shic_xiangke[0].strip()
			else:
				shicai['shic_xiangke'] = ''

			shicai_all.append(shicai)

		step_pattern = re.compile('<li id="make.*?<img alt="(.*?)" data-src="(.*?)".*?<p><span class="index">(.*?)</span>(.*?)</p></li>', re.S)

		# 所有食谱步骤
		stepsmatch = re.findall(step_pattern, recipeHtml)

		steps = []
		for step in stepsmatch:
			# 每一步的说明与图片
			item = {
				'step_img_alt' : step[0].strip(),
				'step_img_src' : step[1].strip(),
				'step_index' : step[2].strip().split('.')[0],
				'step_describe' : step[3].strip()
			}
			steps.append(item)
			
		recipe['steps'] = steps
		recipe['shicais'] = shicai_all
		return recipe
	# 获取菜谱的分类
	def recipesCategory(self, recipe_type):
		url = 'https://www.xiangha.com/' + recipe_type

		recipesContent = self.scapyFunction(url)
		recipe_category_title_pattern = ''
		recipe_category_detail_pattern = ''

		# 常见分类
		if recipe_type == 'fenlei':
			recipe_category_title_pattern = re.compile('<dl><dt><h2 class="kw"><a.*?>(.*?)</a></h2></dt><dd>(.*?)</dd></dl>', re.S)
			recipe_category_detail_pattern = re.compile('<p class="kw"><a.*?href="(.*?)".*?>(.*?)</a></p>', re.S)
		# 其他
		elif recipe_type == 'caipu':
			recipe_category_title_pattern = re.compile('<h3>(.*?)</h3><ul class="clearfix">(.*?)</ul>',re.S)
			recipe_category_detail_pattern = re.compile('<li><a href="(.*?)".*?>(.*?)</a></li>',re.S)
		elif recipe_type == 'shicai':
			recipe_category_title_pattern = re.compile('<div class="rec_classify_cell clearfix"><h3.*?><a href="(.*?)">(.*?)</a></h3>(.*?)</div>',re.S)
			recipe_category_subtitle_pattern = re.compile('<ul class="clearfix">(.*?)</ul>',re.S)
			recipe_category_detail_pattern = re.compile('<li.*?<a href="(.*?)".*?>(.*?)</a>.*?</li>',re.S)
		else: 
			recipe_category_title_pattern = re.compile('<div class="rec_classify_cell clearfix"><h3.*?>(.*?)</h3><ul class="clearfix">(.*?)</ul></div>',re.S)
			recipe_category_detail_pattern = re.compile('<li><a href="(.*?)".*?>(.*?)</a></li>',re.S)

		categoryTitles = re.findall(recipe_category_title_pattern, recipesContent)

		category_all = {}
		category_all_subs = []
		for item in categoryTitles:
			category = {}
			category_detail_content = ''
			category['category_url'] = item[0].strip() if recipe_type == 'shicai' else ''
			category['category_title'] = item[1].strip() if recipe_type == 'shicai' else item[0].strip()
			category_detail_content = item[2].strip() if recipe_type == 'shicai' else item[1].strip()
			pattern = recipe_category_subtitle_pattern if recipe_type == 'shicai' else recipe_category_detail_pattern
			categoryDetail = re.findall(pattern, category_detail_content)

			subs = []
			sub_detail = {}
			for detail in categoryDetail:

				if recipe_type == 'shicai':
					shicai_sub = []
					shicai_detail = re.findall(recipe_category_detail_pattern, detail)

					for shicai in shicai_detail:
						sub = {
							'category_sub_href' : shicai[0].strip(),
							'category_sub_title': shicai[1].strip()
						}
						shicai_sub.append(sub)
					sub_detail[shicai_detail[0][1]] = shicai_sub
				else:
					sub = {
						'category_sub_href' : detail[0].strip(),
						'category_sub_title': detail[1].strip()
					}
					subs.append(sub)

			category['category_subs'] = sub_detail if recipe_type == 'shicai' else subs
			category_all_subs.append(category)

		category_all['recipe_type'] = recipe_type
		category_all['subs'] = category_all_subs

		self.mydb.category_list.insert_one(category_all)
		print(recipe_type)
		# return category_all

	def lunch(self, page):
		url = self.baseURL + 'c-zhongcan' + '/hot-' + str(page)
		mealsListLunch = self.mealsList(url,'c-zhongcan')
		if mealsListLunch is None:
			return -1

		for meal in mealsListLunch:
 			recipeStep = self.recipeSteps(meal['recipe_href'])
 			self.mydb.c_zhongcan_steps.insert_one(recipeStep)
 		return 0

 	def breakfirstList(self, page):
 		url = self.baseURL + 'c-zaocan' + '/hot-' + str(page)
 		mealsListBreaklist = self.mealsList(url,'c-zhongcan')
 		if mealsListBreaklist is None:
 			return -1

 		for meal in mealsListBreaklist:
 			recipeStep = self.recipeSteps(meal['recipe_href'])
 			self.mydb.c_zaocan_steps.insert_one(recipeStep)
 		return 0

 	def dinner(self, page):
 		url = self.baseURL + 'c-wancan' + '/hot-' + str(page)
 		mealsListDinner = self.mealsList(url,'c-zhongcan')
 		if mealsListDinner is None:
 			return -1

 		for meal in mealsListDinner:
 			recipeStep = self.recipeSteps(meal['recipe_href'])
 			self.mydb.c_wancan_steps.insert_one(recipeStep)
 		return 0

 	def saveBreakfirst(self, threadName, delay):
 		breakfirstPage = 1
		while self.breakfirstList(breakfirstPage) == 0:
			breakfirstPage = breakfirstPage + 1
			print delay
			time.sleep(delay)
		else:
			print '结束'

	def saveLunch(self, threadName, delay):
		lunchPage = 1
		while self.lunch(lunchPage) == 0:
			lunchPage = lunchPage + 1
			print delay
			time.sleep(delay)

	def saveDinner(self, threadName, delay):
		dinnerPage = 1
		while self.dinner(dinnerPage) == 0:
			dinnerPage = dinnerPage + 1
			print delay
			time.sleep(delay)

	def categoryList(self):
		# fenlei = self.recipesCategory('fenlei')['subs']
		# if fenlei is None:
		# 	pass
		# else:
		# 	for categorySubs in fenlei:

		# 		category_title = categorySubs['category_title']
		# 		category_url = categorySubs['category_url']
		# 		category = categorySubs['category_subs']
		# 		for sub in category:
		# 			category_sub_href = sub['category_sub_href']
		# 			category_sub_title = sub['category_sub_title']
		# 			category_identifier = category_sub_href.split('/')[-2]
		# 			page = 1
		# 			while page < 11:
		# 				temp_url = category_sub_href + 'hot-' + str(page)
		# 				mealsListDinner = self.mealsList(temp_url,category_identifier)
 	# 					if mealsListDinner is None:
 	# 						pass
 	# 					else:
 	# 						for meal in mealsListDinner:
 	# 							recipeStep = self.recipeSteps(meal['recipe_href'])
 	# 							self.mydb[category_identifier + '_steps'].insert_one(recipeStep)
 	# 					page = page + 1

		self.recipesCategory('fenlei')
		self.recipesCategory('caipu')
		self.recipesCategory('shicai')
		self.recipesCategory('jiankang')


	def meals(self):
		try:
			thread.start_new_thread(self.saveBreakfirst,("thread_breakfirst",random.randint(5,9) + random.randint(0,9)))
		except Exception as e:
			if hasattr(e, 'reason'):
				print '线程出错	', e.reason
			else:
				print '线程出错'

		try:
			thread.start_new_thread(self.saveLunch,("thread_lunch",random.randint(5,9) + random.randint(0,9)))
		except Exception as e:
			if hasattr(e, 'reason'):
				print '线程出错	', e.reason
			else:
				print '线程出错'

		try:
			thread.start_new_thread(self.saveDinner,("thread_dinner",random.randint(5,9) + random.randint(0,9)))
		except Exception as e:
			if hasattr(e, 'reason'):
				print '线程出错	', e.reason
			else:
				print '线程出错'

	def start(self):
		# self.meals()
		self.categoryList()
		# self.recipesCategory('caipu')


		


		
spider = XiangHaRecipe()
spider.start()

while 1:
	pass
